import inspect

from modal_service.app import _generate_qwen_masters, _load_qwen_pipeline


def test_user_generation_never_downloads_or_rebuilds_the_pipeline():
    generation_source = inspect.getsource(_generate_qwen_masters)
    loader_source = inspect.getsource(_load_qwen_pipeline)

    assert "from_pretrained" not in generation_source
    assert "load_lora_weights" not in generation_source
    assert "huggingface_hub" not in generation_source
    assert "huggingface_hub" not in loader_source
    assert "local_files_only=True" in loader_source
