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
        """Create the glossary from the default YAML template."""
        try:
            self._manager.create_glossary_from_markdown()
        except FileNotFoundError:
            print("ℹ️  No glossary YAML found. Run 'create-templates' first.")

    def create_terms(self):
        """No-op — terms are created as part of create_glossary_from_markdown."""
        pass

    def apply(self):
        """Link glossary terms to BigQuery/Iceberg table entries."""
        try:
            self._manager.apply_glossary_to_assets()
        except FileNotFoundError:
            print("ℹ️  No glossary YAML found. Run 'create-templates' first.")
