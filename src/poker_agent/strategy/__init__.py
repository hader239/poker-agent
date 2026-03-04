"""Strategy engines for poker decision-making."""

from poker_agent.config import AgentConfig
from poker_agent.strategy.base import Strategy
from poker_agent.strategy.gto_strategy import GTOStrategy
from poker_agent.strategy.llm_strategy import LLMStrategy


def create_strategy(config: AgentConfig) -> Strategy:
    """Factory function to create the appropriate strategy engine."""
    if config.strategy_type == "llm":
        return LLMStrategy(config)
    elif config.strategy_type == "gto":
        return GTOStrategy()
    else:
        raise ValueError(f"Unknown strategy type: {config.strategy_type}")


__all__ = ["GTOStrategy", "LLMStrategy", "Strategy", "create_strategy"]
