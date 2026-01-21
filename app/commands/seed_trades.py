"""
CLI Command: Seed Trades from CSV

Parses TradingView alert CSV exports and seeds missing trades into the database.

Usage:
    python -m app.commands.seed_trades <csv_path> [options]

Options:
    --dry-run       Show what would be done without making changes (default)
    --live          Actually make changes to the database
    --exits-only    Only process exit signals for stuck trades
    --entries-only  Only reconstruct missing entries
    --after DATE    Only process signals after this date (YYYY-MM-DD)
    --verbose       Enable verbose output

Examples:
    # Preview what would be done
    python -m app.commands.seed_trades "tradingview alerts.csv" --dry-run

    # Process only exit signals (close stuck trades)
    python -m app.commands.seed_trades "tradingview alerts.csv" --live --exits-only

    # Process signals after Jan 17, 2026
    python -m app.commands.seed_trades "tradingview alerts.csv" --live --after 2026-01-17

    # Full reconstruction (live mode)
    python -m app.commands.seed_trades "tradingview alerts.csv" --live
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    parser = argparse.ArgumentParser(
        description='Seed missing trades from TradingView CSV export',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        'csv_path',
        help='Path to the TradingView alerts CSV file'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=True,
        help='Show what would be done without making changes (default)'
    )
    parser.add_argument(
        '--live',
        action='store_true',
        help='Actually make changes to the database'
    )
    parser.add_argument(
        '--exits-only',
        action='store_true',
        help='Only process exit signals for stuck open trades'
    )
    parser.add_argument(
        '--entries-only',
        action='store_true',
        help='Only reconstruct missing entry signals'
    )
    parser.add_argument(
        '--after',
        type=str,
        help='Only process signals after this date (YYYY-MM-DD format)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Determine dry_run mode (--live overrides --dry-run)
    dry_run = not args.live

    # Parse cutoff date
    cutoff_date = None
    if args.after:
        try:
            cutoff_date = datetime.strptime(args.after, '%Y-%m-%d')
            cutoff_date = cutoff_date.replace(tzinfo=timezone.utc)
        except ValueError:
            logger.error(f"Invalid date format: {args.after}. Use YYYY-MM-DD")
            sys.exit(1)

    # Determine what to process
    process_exits = not args.entries_only
    process_entries = not args.exits_only

    # Import here to avoid circular imports and allow DB connection
    from app.database import db
    from app.services.csv_seeder import CSVSeeder

    # Connect to database
    await db.connect()

    try:
        # Create seeder
        seeder = CSVSeeder(cutoff_date=cutoff_date)

        # Print summary before processing
        print("\n" + "=" * 60)
        print("TRADE SEEDER - TradingView CSV Import")
        print("=" * 60)
        print(f"CSV File: {args.csv_path}")
        print(f"Mode: {'DRY RUN (preview only)' if dry_run else 'LIVE (will modify database)'}")
        print(f"Process Exits: {process_exits}")
        print(f"Process Entries: {process_entries}")
        if cutoff_date:
            print(f"After Date: {cutoff_date.strftime('%Y-%m-%d')}")
        print("=" * 60 + "\n")

        if not dry_run:
            confirm = input("This will MODIFY the database. Type 'yes' to continue: ")
            if confirm.lower() != 'yes':
                print("Aborted.")
                sys.exit(0)

        # Run seeding
        result = await seeder.seed(
            csv_path=args.csv_path,
            dry_run=dry_run,
            process_exits=process_exits,
            process_entries=process_entries
        )

        # Print results
        print("\n" + "=" * 60)
        print("RESULTS")
        print("=" * 60)
        print(f"Total signals parsed: {result.total_signals}")
        print(f"  - Entry signals: {result.entries_found}")
        print(f"  - Exit signals: {result.exits_found}")
        print("")
        print(f"Exits processed: {result.exits_processed}")
        print(f"Trades created: {result.trades_created}")
        print(f"Entries reconstructed: {result.entries_reconstructed}")
        print("")
        print(f"Skipped (no matching open trade): {result.skipped_no_match}")
        print(f"Skipped (already closed): {result.skipped_already_closed}")
        print(f"Skipped (trade already exists): {result.skipped_already_exists}")

        if result.errors:
            print(f"\nErrors ({len(result.errors)}):")
            for error in result.errors[:10]:  # Show first 10
                print(f"  - {error}")
            if len(result.errors) > 10:
                print(f"  ... and {len(result.errors) - 10} more")

        print("=" * 60)

        if dry_run:
            print("\nThis was a DRY RUN. No changes were made.")
            print("Run with --live to apply changes.\n")
        else:
            print("\nChanges have been applied to the database.\n")

    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
