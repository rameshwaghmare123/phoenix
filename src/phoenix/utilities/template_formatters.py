import re
from abc import ABC, abstractmethod
from string import Formatter
from typing import Any, Iterable, Set


class TemplateFormatter(ABC):
    @abstractmethod
    def parse(self, template: str) -> Set[str]:
        """
        Parse the template and return a set of variable names.
        """
        raise NotImplementedError

    def format(self, template: str, **variables: Any) -> str:
        """
        Formats the template with the given variables.
        """
        template_variable_names = self.parse(template)
        if missing_template_variables := template_variable_names - set(variables.keys()):
            raise ValueError(f"Missing template variables: {', '.join(missing_template_variables)}")
        return self._format(template, template_variable_names, **variables)

    @abstractmethod
    def _format(self, template: str, variable_names: Iterable[str], **variables: Any) -> str:
        raise NotImplementedError


class FStringTemplateFormatter(TemplateFormatter):
    """
    Regular f-string template formatter.

    Examples:

    >>> formatter = FStringTemplateFormatter()
    >>> formatter.format("{hello}", hello="world")
    'world'
    """

    def parse(self, template: str) -> Set[str]:
        return set(field_name for _, field_name, _, _ in Formatter().parse(template) if field_name)

    def _format(self, template: str, variable_names: Iterable[str], **variables: Any) -> str:
        return template.format(**variables)


class MustacheTemplateFormatter(TemplateFormatter):
    """
    Mustache template formatter.

    Examples:

    >>> formatter = MustacheTemplateFormatter()
    >>> formatter.format("{{ hello }}", hello="world")
    'world'
    """

    PATTERN = re.compile(r"(?<!\\){{\s*(\w+)\s*}}")

    def parse(self, template: str) -> Set[str]:
        return set(match for match in re.findall(self.PATTERN, template))

    def _format(self, template: str, variable_names: Iterable[str], **variables: Any) -> str:
        for variable_name in variable_names:
            template = re.sub(
                pattern=rf"(?<!\\){{{{\s*{variable_name}\s*}}}}",
                repl=variables[variable_name],
                string=template,
            )
        return template
