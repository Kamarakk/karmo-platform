"""The 7 worked examples required by the Core v2 Engineering Blueprint
Program, Workstream 3. All synthetic -- no example here connects to any
real broker, social platform, BloomBoss system, infrastructure, or
production KARMO. Every one is a plain dict manifest, valid input to
ToolRegistry.register().
"""

from registry import CapabilityClass


def _base(**overrides):
    manifest = {
        "tool_id": "example.base.tool",
        "domain": "example",
        "version": "1.0.0",
        "description": "base example, overridden per case",
        "input_schema": {"type": "object", "properties": {}},
        "output_schema": {"type": "object", "properties": {}},
        "capability_class": CapabilityClass.READ,
        "read_scope": [],
        "write_scope": [],
        "external_side_effects": False,
        "financial_action": False,
        "destructive_action": False,
        "network_requirements": [],
        "secret_requirements": [],
        "invocation_identity": None,
        "timeout_seconds": 10,
        "retry_policy": {"max_attempts": 1, "backoff": "none"},
        "idempotent": True,
        "idempotency_mechanism": "read-only, trivially idempotent",
        "rollback_or_compensation": "N/A -- nothing changed",
        "health_check": "N/A",
        "deprecation_policy": "superseded_by field once a v2 exists",
        "dependencies": [],
        "observability": "logged to the invocation ledger",
        "failure_isolation": "scoped to its own domain's credentials only",
    }
    manifest.update(overrides)
    return manifest


def example_a_harmless_read_only():
    """A. Harmless read-only tool."""
    return _base(
        tool_id="karmolab.infra.get_service_status",
        domain="karmolab",
        description="Read the reported status of a named KarmoLab-monitored service.",
        capability_class=CapabilityClass.READ,
        read_scope=["karmolab.infra.status"],
    )


def example_b_bloomboss_inventory_read():
    """B. BloomBoss inventory read."""
    return _base(
        tool_id="bloomboss.inventory.read_stock_level",
        domain="bloomboss",
        description="Read the current recorded stock level for one SKU.",
        capability_class=CapabilityClass.READ,
        read_scope=["bloomboss.inventory"],
    )


def example_c_bloomboss_inventory_mutation():
    """C. BloomBoss inventory mutation (business mutation, financial)."""
    return _base(
        tool_id="bloomboss.inventory.record_sale",
        domain="bloomboss",
        description="Record a completed sale, decrementing inventory and creating a revenue-recognized transaction.",
        capability_class=CapabilityClass.REVERSIBLE_WRITE,
        read_scope=["bloomboss.inventory", "bloomboss.products"],
        write_scope=["bloomboss.inventory", "bloomboss.sales"],
        financial_action=True,
        invocation_identity="uuid5(bloomboss.sale, order_id)",
        idempotent=True,
        idempotency_mechanism="order_id uniqueness constraint; retry is a no-op on conflict",
        rollback_or_compensation="compensating void_sale tool, itself its own gated REVERSIBLE_WRITE tool",
    )


def example_d_external_social_posting():
    """D. External social-media posting."""
    return _base(
        tool_id="bloomboss.social.post_update",
        domain="bloomboss",
        description="Post a marketing update to a connected social account.",
        capability_class=CapabilityClass.EXTERNAL_ACTION,
        write_scope=["bloomboss.social"],
        external_side_effects=True,
        network_requirements=["social-platform-api.example (synthetic, not connected)"],
        secret_requirements=["bloomboss.social.api_token_ref"],
        rollback_or_compensation="a delete/edit tool exists but is itself its own audited action -- the post having been publicly visible is not undone",
    )


def example_e_infrastructure_mutation():
    """E. Infrastructure mutation (destructive)."""
    return _base(
        tool_id="karmolab.infra.restart_service",
        domain="karmolab",
        description="Restart a named KarmoLab-monitored service.",
        capability_class=CapabilityClass.DESTRUCTIVE_HIGH_IMPACT,
        write_scope=["karmolab.infra"],
        destructive_action=True,
        rollback_or_compensation="N/A -- a restart's downtime window cannot be undone; evaluated per-service",
    )


def example_f_financial_market_data_read():
    """F. Financial market-data read."""
    return _base(
        tool_id="finance.market_data.get_quote",
        domain="finance",
        description="Read the latest available quote for one symbol from a market-data provider.",
        capability_class=CapabilityClass.READ,
        read_scope=["finance.market_data"],
        network_requirements=["market-data-api.example (synthetic, not connected)"],
        financial_action=False,  # a read has no execution consequence of its own
    )


def example_g_proposed_trade_execution():
    """G. Proposed trade execution -- MUST require EXPLICIT_PER_CALL,
    proven by test, not merely asserted here."""
    return _base(
        tool_id="finance.trading.place_order",
        domain="finance",
        description="Place a trade order with a connected broker, exact parameters bound to a prior explicit approval.",
        capability_class=CapabilityClass.DESTRUCTIVE_HIGH_IMPACT,
        write_scope=["finance.orders"],
        destructive_action=True,
        financial_action=True,
        network_requirements=["broker-api.example (synthetic, not connected)"],
        secret_requirements=["finance.broker.api_key_ref"],
        invocation_identity="uuid5(finance.order, approval_id) -- one order per approval, never re-derivable from order args alone",
        idempotent=True,
        idempotency_mechanism="broker client-order-id bound 1:1 to the approval_id that authorized it",
        rollback_or_compensation="N/A -- a filled order cannot be un-filled; only a new, separately-approved compensating trade is possible",
    )


ALL_EXAMPLES = {
    "A": example_a_harmless_read_only,
    "B": example_b_bloomboss_inventory_read,
    "C": example_c_bloomboss_inventory_mutation,
    "D": example_d_external_social_posting,
    "E": example_e_infrastructure_mutation,
    "F": example_f_financial_market_data_read,
    "G": example_g_proposed_trade_execution,
}
