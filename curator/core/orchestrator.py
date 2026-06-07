"""Orchestrator for running agents."""
import os
from typing import Optional
from dotenv import load_dotenv

from .config import load_config, CuratorConfig
from .db import init_db, get_deals
from .notifier import notify_deals
from ..agents.steam_agent import SteamAgent

# Load environment variables
load_dotenv()


# Registry of all available agents
AGENT_REGISTRY = {
    "steam": SteamAgent,
}


def run_all(agent_ids: Optional[list[str]] = None) -> dict:
    """Run all enabled agents or specific agents.

    Args:
        agent_ids: Optional list of agent IDs to run. If None, runs all enabled agents.

    Returns:
        Dictionary with results for each agent run.
    """
    # Initialize DB and load config
    init_db()
    config = load_config()

    results = {}
    new_deals = []

    # Determine which agents to run
    if agent_ids:
        agents_to_run = agent_ids
    else:
        agents_to_run = [a.id for a in config.agents if a.enabled]

    # Run each agent
    for agent_id in agents_to_run:
        if agent_id not in AGENT_REGISTRY:
            results[agent_id] = {
                "status": "error",
                "error": f"Unknown agent: {agent_id}",
            }
            continue

        # Get agent config
        agent_config = None
        for a in config.agents:
            if a.id == agent_id:
                agent_config = a
                break

        if not agent_config:
            results[agent_id] = {
                "status": "error",
                "error": f"Agent {agent_id} not found in config",
            }
            continue

        if not agent_config.enabled and agent_ids is None:
            # Skip disabled agents unless explicitly requested
            continue

        # Instantiate and run agent
        agent_class = AGENT_REGISTRY[agent_id]
        agent = agent_class(config)

        print(f"Running agent: {agent_id}")
        result = agent.run()
        results[agent_id] = result

        # Collect new deals for notifications
        if result["status"] == "success" and result["deals_found"] > 0:
            # Get the deals we just found
            recent_deals = get_deals(agent_id=agent_id, limit=result["deals_found"])
            new_deals.extend(recent_deals)

    # Send notifications for all new deals
    if new_deals:
        print(f"Sending notifications for {len(new_deals)} new deals")
        notify_deals(config, new_deals)

    return {
        "results": results,
        "total_deals": len(new_deals),
    }


def main():
    """Entry point for CLI execution."""
    result = run_all()

    print("\n" + "=" * 50)
    print("CURATOR RUN SUMMARY")
    print("=" * 50)

    for agent_id, agent_result in result["results"].items():
        status = agent_result["status"]
        if status == "success":
            print(f"✓ {agent_id}: {agent_result['deals_found']} deals found")
        else:
            error = agent_result.get("error", "Unknown error")
            print(f"✗ {agent_id}: {error}")

    print(f"\nTotal deals: {result['total_deals']}")
    print("=" * 50)


if __name__ == "__main__":
    main()
