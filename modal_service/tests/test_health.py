from modal_service.health import generation_payload, generation_ready, ready_payload


def test_generation_health_is_not_ready_until_every_generation_dependency_exists():
    assert not generation_ready(generation_enabled=False, templates_installed=True, model_configured=True)
    assert not generation_ready(generation_enabled=True, templates_installed=False, model_configured=True)
    assert not generation_ready(generation_enabled=True, templates_installed=True, model_configured=False)
    assert generation_ready(generation_enabled=True, templates_installed=True, model_configured=True)


def test_api_readiness_does_not_claim_gpu_generation_readiness():
    ready = ready_payload(service="gru-mascot", environment="production", model_configured=True)
    generation = generation_payload(
        service="gru-mascot",
        environment="production",
        generation_enabled=False,
        templates_installed=False,
        model_configured=True,
    )

    assert ready["status"] == "ready"
    assert generation["status"] == "not_ready"
    assert generation["capabilities"]["master"]["ready"] is False
    assert generation["capabilities"]["poses"]["ready"] is False


def test_generation_health_distinguishes_master_from_pose_template_readiness():
    generation = generation_payload(
        service="gru-mascot",
        environment="production",
        generation_enabled=True,
        templates_installed=False,
        model_configured=True,
    )

    assert generation["status"] == "not_ready"
    assert generation["capabilities"]["master"]["ready"] is True
    assert generation["capabilities"]["poses"]["ready"] is False
