import sys
import pytest
import factory
from pytest_factoryboy import register

from chat.models import User


@pytest.hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config):
    if "xdist" not in sys.modules:
        return
    if config.option.file_or_dir and len(config.option.file_or_dir) == 1 and "::" in config.option.file_or_dir[0]:
        # if just running one test then disable xdist as generally this will be faster
        config.option.dist = "no"
        config.option.numprocesses = 0


@pytest.fixture(autouse=True)
def enable_db_access(db):
    pass


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    name = factory.Faker("first_name")
    school_mascot = factory.Faker("word")


# register factories as fixtures
register(UserFactory)
