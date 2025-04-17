from django.forms import ValidationError
import pytest
from chat.models import GroupStrategyPhasesThatAllowConfig, GroupStrategyPhaseConfig


def test_group_strategy_phase_config_cleaning():
    GroupStrategyPhaseConfig.objects.all().delete()

    # valid range
    config = GroupStrategyPhaseConfig.objects.create(
        group_strategy_phase=GroupStrategyPhasesThatAllowConfig.AFTER_AUDIENCE,
        min_wait_seconds=1,
        max_wait_seconds=2,
    )
    config.clean()
    assert True, "validation passes"

    # equal values
    GroupStrategyPhaseConfig.objects.all().delete()
    config = GroupStrategyPhaseConfig.objects.create(
        group_strategy_phase=GroupStrategyPhasesThatAllowConfig.AFTER_AUDIENCE,
        min_wait_seconds=1,
        max_wait_seconds=1,
    )
    config.clean()
    assert True, "validation passes"

    # negative value
    GroupStrategyPhaseConfig.objects.all().delete()
    config = GroupStrategyPhaseConfig.objects.create(
        group_strategy_phase=GroupStrategyPhasesThatAllowConfig.AFTER_AUDIENCE,
        min_wait_seconds=-1,
        max_wait_seconds=2,
    )
    with pytest.raises(ValidationError):
        config.clean()

    # min greater than max
    GroupStrategyPhaseConfig.objects.all().delete()
    config = GroupStrategyPhaseConfig.objects.create(
        group_strategy_phase=GroupStrategyPhasesThatAllowConfig.AFTER_AUDIENCE,
        min_wait_seconds=2,
        max_wait_seconds=1,
    )
    with pytest.raises(ValidationError):
        config.clean()
