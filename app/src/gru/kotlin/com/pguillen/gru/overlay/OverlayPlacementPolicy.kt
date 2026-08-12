package com.pguillen.gru.overlay

import kotlin.math.max

internal data class OverlayPoint(val x: Int, val y: Int)

internal data class OverlaySize(val width: Int, val height: Int)

internal data class OverlayRect(
    val left: Int,
    val top: Int,
    val right: Int,
    val bottom: Int,
) {
    val width: Int get() = (right - left).coerceAtLeast(0)
    val height: Int get() = (bottom - top).coerceAtLeast(0)

    fun expanded(pixels: Int): OverlayRect = OverlayRect(
        left - pixels,
        top - pixels,
        right + pixels,
        bottom + pixels,
    )

    fun intersects(other: OverlayRect): Boolean =
        left < other.right && right > other.left && top < other.bottom && bottom > other.top
}

internal enum class AvoidanceKind { IME, EDITOR, CRITICAL }

internal data class AvoidanceRegion(val bounds: OverlayRect, val kind: AvoidanceKind)

internal data class OverlayEnvironment(
    val usableBounds: OverlayRect,
    val avoidanceRegions: List<AvoidanceRegion>,
)

/** Pure placement policy. Android collection and window mutation stay outside this class. */
internal object OverlayPlacementPolicy {
    fun initialPosition(environment: OverlayEnvironment, size: OverlaySize, margin: Int): OverlayPoint {
        val usable = environment.usableBounds
        val preferred = OverlayPoint(
            x = usable.right - size.width - margin,
            y = usable.top + ((usable.height * 0.60f) - size.height / 2f).toInt(),
        )
        return resolve(preferred, environment, size, margin)
    }

    fun resolve(
        preferred: OverlayPoint,
        environment: OverlayEnvironment,
        size: OverlaySize,
        margin: Int,
    ): OverlayPoint {
        val clamped = clamp(preferred, environment.usableBounds, size, margin)
        if (isSafe(clamped, environment, size, margin)) return clamped

        val candidates = buildList {
            add(initialCandidate(environment.usableBounds, size, margin))
            environment.avoidanceRegions.forEach { region ->
                val blocked = region.bounds.expanded(margin)
                add(OverlayPoint(clamped.x, blocked.top - size.height))
                add(OverlayPoint(clamped.x, blocked.bottom))
                add(OverlayPoint(blocked.left - size.width, clamped.y))
                add(OverlayPoint(blocked.right, clamped.y))
                add(OverlayPoint(environment.usableBounds.left + margin, blocked.top - size.height))
                add(OverlayPoint(environment.usableBounds.right - size.width - margin, blocked.top - size.height))
            }
        }.map { clamp(it, environment.usableBounds, size, margin) }
            .distinct()
            .filter { isSafe(it, environment, size, margin) }

        return candidates.minByOrNull { squaredDistance(it, clamped) }
            ?: scanForSafePosition(clamped, environment, size, margin)
            ?: clamped
    }

    fun dragBounds(environment: OverlayEnvironment, size: OverlaySize, margin: Int): OverlayRect {
        val usable = environment.usableBounds
        val imeTop = environment.avoidanceRegions
            .filter { it.kind == AvoidanceKind.IME }
            .minOfOrNull { it.bounds.top }
            ?: usable.bottom
        return OverlayRect(
            left = usable.left + margin,
            top = usable.top + margin,
            right = (usable.right - size.width - margin).coerceAtLeast(usable.left + margin),
            bottom = (imeTop - size.height - margin).coerceAtLeast(usable.top + margin),
        )
    }

    fun isSafe(
        point: OverlayPoint,
        environment: OverlayEnvironment,
        size: OverlaySize,
        margin: Int,
    ): Boolean {
        val usable = environment.usableBounds
        val view = OverlayRect(point.x, point.y, point.x + size.width, point.y + size.height)
        val inside = view.left >= usable.left + margin && view.top >= usable.top + margin &&
            view.right <= usable.right - margin && view.bottom <= usable.bottom - margin
        return inside && environment.avoidanceRegions.none { view.intersects(it.bounds.expanded(margin)) }
    }

    private fun initialCandidate(usable: OverlayRect, size: OverlaySize, margin: Int) = OverlayPoint(
        usable.right - size.width - margin,
        usable.top + ((usable.height * 0.60f) - size.height / 2f).toInt(),
    )

    private fun clamp(point: OverlayPoint, usable: OverlayRect, size: OverlaySize, margin: Int): OverlayPoint {
        val minX = usable.left + margin
        val minY = usable.top + margin
        val maxX = max(minX, usable.right - size.width - margin)
        val maxY = max(minY, usable.bottom - size.height - margin)
        return OverlayPoint(point.x.coerceIn(minX, maxX), point.y.coerceIn(minY, maxY))
    }

    private fun scanForSafePosition(
        preferred: OverlayPoint,
        environment: OverlayEnvironment,
        size: OverlaySize,
        margin: Int,
    ): OverlayPoint? {
        val usable = environment.usableBounds
        val step = max(8, minOf(size.width, size.height) / 4)
        val candidates = mutableListOf<OverlayPoint>()
        var y = usable.top + margin
        while (y <= usable.bottom - size.height - margin) {
            var x = usable.left + margin
            while (x <= usable.right - size.width - margin) {
                val point = OverlayPoint(x, y)
                if (isSafe(point, environment, size, margin)) candidates += point
                x += step
            }
            y += step
        }
        return candidates.minByOrNull { squaredDistance(it, preferred) }
    }

    private fun squaredDistance(a: OverlayPoint, b: OverlayPoint): Long {
        val dx = (a.x - b.x).toLong()
        val dy = (a.y - b.y).toLong()
        return dx * dx + dy * dy
    }
}
