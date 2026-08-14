import pytest
from pydantic import ValidationError

from app.application.commands.application_command import ApplicationCommand
from app.application.commands.command_registry import CommandRegistry


def _command(name: str = "executive_dashboard") -> ApplicationCommand:
    return ApplicationCommand(
        name=name, description="Build.", enabled=True, operation_name=name
    )


def test_commands_field_preserva_api_publica():
    command = _command()

    registry = CommandRegistry(commands=(command,))

    assert registry.commands == (command,)


def test_commands_default_e_tupla_vazia():
    registry = CommandRegistry()

    assert registry.commands == ()


def test_registro_adds_the_given_command():
    command = _command()
    registry = CommandRegistry()

    updated = registry.register(command)

    assert updated.commands == (command,)
    assert registry.commands == ()


def test_register_many_adds_every_given_command_in_order():
    command_a = _command("alpha")
    command_b = _command("beta")
    registry = CommandRegistry()

    updated = registry.register_many([command_a, command_b])

    assert updated.commands == (command_a, command_b)


def test_find_existente_returns_the_matching_command():
    command = _command()
    registry = CommandRegistry(commands=(command,))

    assert registry.find("executive_dashboard") is command


def test_find_inexistente_returns_none():
    registry = CommandRegistry(commands=(_command(),))

    assert registry.find("does_not_exist") is None


def test_exists_true_and_false():
    registry = CommandRegistry(commands=(_command(),))

    assert registry.exists("executive_dashboard") is True
    assert registry.exists("does_not_exist") is False


def test_list_returns_the_registered_commands_in_order():
    command_a = _command("alpha")
    command_b = _command("beta")
    registry = CommandRegistry(commands=(command_a, command_b))

    assert registry.list() == [command_a, command_b]


def test_imutabilidade_rejects_attribute_assignment():
    registry = CommandRegistry(commands=(_command(),))

    with pytest.raises(ValidationError):
        registry.commands = ()
