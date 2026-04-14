"""Legacy glossary writer — delegates to BusinessGlossaryManager.

Retained for backward-compatibility with the ``catalog()`` CLI command.
New code should use ``ingestion.glossary_manager.BusinessGlossaryManager`` directly.
"""

from generators.config import GeneratorConfig
from ingestion.glossary_manager import BusinessGlossaryManager


class GlossaryWriter:
    """Thin wrapper that delegates to :class:`BusinessGlossaryManager`."""

    def __init__(self, config: GeneratorConfig):
        self.config = config
        self._manager = BusinessGlossaryManager(config)

    def create_glossary(self):
        """Create the glossary from the default markdown template."""
        try:
            self._manager.create_glossary_from_markdown()
        except FileNotFoundError:
            print("ℹ️  No glossary markdown found. Run 'create-templates' first.")

    def create_terms(self):
        """No-op — terms are created as part of create_glossary_from_markdown."""
        pass
