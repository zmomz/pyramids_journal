"""
Test script to generate a sample equity curve chart with stats footer.
Run with: python test_equity_curve.py
"""

import io
from datetime import datetime, timedelta
from dataclasses import dataclass


@dataclass
class EquityPoint:
    """Single point on equity curve."""
    timestamp: datetime
    cumulative_pnl: float


@dataclass
class ChartStats:
    """Statistics for equity curve chart footer."""
    total_net_pnl: float = 0.0
    max_drawdown_percent: float = 0.0
    max_drawdown_usdt: float = 0.0
    num_trades: int = 0
    win_rate: float = 0.0
    total_used_equity: float = 0.0
    profit_factor: float = 0.0
    win_loss_ratio: float = 0.0


def generate_equity_curve_image(
    equity_points: list[EquityPoint],
    date: str,
    chart_stats: ChartStats | None = None,
    logo_path: str | None = None
) -> io.BytesIO | None:
    """
    Generate a professional equity curve chart image with stats footer.
    """
    if len(equity_points) < 2:
        return None

    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from matplotlib.ticker import FuncFormatter
        from matplotlib.patches import FancyBboxPatch
        import matplotlib.gridspec as gridspec
        from matplotlib.offsetbox import OffsetImage, AnnotationBbox
        from PIL import Image
        import os
    except ImportError:
        print("matplotlib not installed. Run: pip install matplotlib")
        return None

    # Extract data
    timestamps = [p.timestamp for p in equity_points]
    cumulative_pnls = [p.cumulative_pnl for p in equity_points]
    final_pnl = cumulative_pnls[-1]

    # Determine color based on final PnL
    line_color = '#00C853' if final_pnl >= 0 else '#FF1744'  # Green or Red

    # Create figure with dark theme
    plt.style.use('dark_background')

    # Figure with stats footer - add extra space at top for header
    # Background color matching logo
    bg_color = '#1c1520'  # Dark purple-black matching logo
    chart_bg = '#16213e'  # Slightly different for chart area

    if chart_stats:
        fig = plt.figure(figsize=(12, 11), dpi=150)
        gs = gridspec.GridSpec(3, 1, height_ratios=[0.7, 3, 1.1], hspace=0.18)
        ax_header = fig.add_subplot(gs[0])
        ax = fig.add_subplot(gs[1])
        ax_footer = fig.add_subplot(gs[2])
    else:
        fig = plt.figure(figsize=(10, 7), dpi=150)
        gs = gridspec.GridSpec(2, 1, height_ratios=[0.8, 4], hspace=0.12)
        ax_header = fig.add_subplot(gs[0])
        ax = fig.add_subplot(gs[1])

    # Set background colors
    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(chart_bg)
    ax_header.set_facecolor(bg_color)
    ax_header.axis('off')

    # Plot the equity curve
    ax.plot(timestamps, cumulative_pnls, color=line_color, linewidth=2.5,
            marker='o', markersize=4, markerfacecolor=line_color, markeredgecolor='white',
            markeredgewidth=0.5, zorder=5)

    # Fill area under curve
    ax.fill_between(timestamps, cumulative_pnls, alpha=0.3, color=line_color)

    # Add horizontal line at zero
    ax.axhline(y=0, color='#ffffff', linewidth=0.8, linestyle='--', alpha=0.4)

    # Format x-axis (time)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    plt.sca(ax)
    plt.xticks(rotation=45, ha='right')

    # Format y-axis (currency)
    def currency_formatter(x, p):
        if x >= 0:
            return f'+${x:,.0f}'
        return f'-${abs(x):,.0f}'
    ax.yaxis.set_major_formatter(FuncFormatter(currency_formatter))

    # Add logo and title in header area
    if logo_path and os.path.exists(logo_path):
        try:
            logo_img = Image.open(logo_path)
            # Resize logo to fit nicely
            logo_img.thumbnail((120, 120), Image.Resampling.LANCZOS)
            imagebox = OffsetImage(logo_img, zoom=0.6)
            ab = AnnotationBbox(imagebox, (0.08, 0.5), frameon=False,
                                xycoords=ax_header.transAxes, box_alignment=(0.5, 0.5))
            ax_header.add_artist(ab)
        except Exception as e:
            print(f"Could not load logo: {e}")

    # Title in header (no overlap now)
    ax_header.text(0.18, 0.65, 'Equity Curve', transform=ax_header.transAxes,
                   fontsize=20, color='white', fontweight='bold', va='center')
    ax_header.text(0.18, 0.25, f'Time vs Cumulative Net PnL (USDT) - {date}',
                   transform=ax_header.transAxes, fontsize=11, color='#888888', va='center')

    # Style the spines
    for spine in ax.spines.values():
        spine.set_color('#404040')
        spine.set_linewidth(1)

    # Grid styling
    ax.grid(True, linestyle='--', alpha=0.2, color='#ffffff')
    ax.tick_params(colors='#b0b0b0', labelsize=9)

    # Add final value annotation (only the last point)
    sign = '+' if final_pnl >= 0 else ''
    annotation_text = f'Cumulative PnL: {sign}${final_pnl:,.2f}'

    ax.annotate(
        annotation_text,
        xy=(timestamps[-1], final_pnl),
        xytext=(15, 15),
        textcoords='offset points',
        fontsize=11,
        fontweight='bold',
        color='white',
        bbox=dict(
            boxstyle='round,pad=0.5',
            facecolor=line_color,
            edgecolor='white',
            linewidth=1,
            alpha=0.9
        ),
        arrowprops=dict(
            arrowstyle='->',
            color='white',
            connectionstyle='arc3,rad=0.2',
            linewidth=1.5
        ),
        zorder=10
    )

    # Highlight final point
    ax.scatter([timestamps[-1]], [final_pnl], color='white', s=80, zorder=6,
               edgecolors=line_color, linewidths=2)

    # Add stats footer if provided
    if chart_stats:
        ax_footer.set_facecolor(bg_color)
        ax_footer.axis('off')

        # Stats box styling
        box_color = '#252540'
        border_color = '#404060'

        # Define stats data for two rows
        row1_stats = [
            ('Total Net PnL (USDT)', f'{"+$" if chart_stats.total_net_pnl >= 0 else "-$"}{abs(chart_stats.total_net_pnl):,.2f}'),
            ('Max Drawdown (%)', f'{chart_stats.max_drawdown_percent:.2f}%'),
            ('Number of Trades', f'{chart_stats.num_trades}'),
            ('Win Rate (%)', f'{chart_stats.win_rate:.2f}%'),
        ]
        row2_stats = [
            ('Total Used Equity (USDT)', f'{chart_stats.total_used_equity:,.2f}'),
            ('Max Drawdown (USDT)', f'-{chart_stats.max_drawdown_usdt:,.2f}'),
            ('Profit Factor', f'{chart_stats.profit_factor:.2f}'),
            ('Win / Loss Ratio', f'{chart_stats.win_loss_ratio:.2f}'),
        ]

        # Draw stat boxes
        box_width = 0.23
        box_height = 0.38
        spacing = 0.01
        start_x = 0.02
        row1_y = 0.55
        row2_y = 0.08

        for row_idx, (stats_row, y_pos) in enumerate([(row1_stats, row1_y), (row2_stats, row2_y)]):
            for i, (label, value) in enumerate(stats_row):
                x_pos = start_x + i * (box_width + spacing)

                # Draw box
                box = FancyBboxPatch(
                    (x_pos, y_pos), box_width, box_height,
                    boxstyle="round,pad=0.02,rounding_size=0.02",
                    facecolor=box_color,
                    edgecolor=border_color,
                    linewidth=1.5,
                    transform=ax_footer.transAxes
                )
                ax_footer.add_patch(box)

                # Add label (smaller, gray)
                ax_footer.text(
                    x_pos + box_width / 2, y_pos + box_height * 0.75,
                    label,
                    transform=ax_footer.transAxes,
                    fontsize=9,
                    color='#888888',
                    ha='center', va='center'
                )

                # Add value (larger, white, bold)
                ax_footer.text(
                    x_pos + box_width / 2, y_pos + box_height * 0.32,
                    value,
                    transform=ax_footer.transAxes,
                    fontsize=14,
                    color='white',
                    fontweight='bold',
                    ha='center', va='center'
                )

    # Tight layout
    plt.tight_layout()

    # Save to BytesIO buffer
    buf = io.BytesIO()
    fig.savefig(buf, format='png', facecolor=fig.get_facecolor(),
                edgecolor='none', bbox_inches='tight', pad_inches=0.2)
    buf.seek(0)

    # Close figure to free memory
    plt.close(fig)

    return buf


def create_sample_data_positive():
    """Create sample equity points for a profitable day."""
    base_time = datetime(2026, 1, 19, 9, 0, 0)

    # Simulate 8 trades throughout the day with cumulative PnL
    trades_pnl = [
        (0, 45.50),      # 09:00 - First trade: +$45.50
        (35, 82.30),     # 09:35 - Second trade: cumulative +$82.30
        (90, 65.20),     # 10:30 - Third trade (small loss): cumulative +$65.20
        (150, 125.80),   # 11:30 - Fourth trade: cumulative +$125.80
        (240, 198.45),   # 13:00 - Fifth trade: cumulative +$198.45
        (320, 245.60),   # 14:20 - Sixth trade: cumulative +$245.60
        (420, 312.85),   # 16:00 - Seventh trade: cumulative +$312.85
        (510, 482.55),   # 17:30 - Eighth trade: cumulative +$482.55
    ]

    equity_points = []
    for minutes, cumulative_pnl in trades_pnl:
        timestamp = base_time + timedelta(minutes=minutes)
        equity_points.append(EquityPoint(
            timestamp=timestamp,
            cumulative_pnl=cumulative_pnl
        ))

    # Sample stats for positive day
    chart_stats = ChartStats(
        total_net_pnl=482.55,
        max_drawdown_percent=12.35,
        max_drawdown_usdt=17.10,
        num_trades=8,
        win_rate=75.00,
        total_used_equity=8000.00,
        profit_factor=2.45,
        win_loss_ratio=1.85,
    )

    return equity_points, chart_stats


def create_sample_data_negative():
    """Create sample equity points for a losing day."""
    base_time = datetime(2026, 1, 19, 9, 0, 0)

    # Simulate trades with negative cumulative PnL
    trades_pnl = [
        (0, -25.30),      # 09:00
        (45, -48.60),     # 09:45
        (120, -32.15),    # 11:00 (small recovery)
        (180, -85.40),    # 12:00
        (270, -110.25),   # 13:30
        (360, -95.80),    # 15:00 (small recovery)
        (450, -141.40),   # 16:30
    ]

    equity_points = []
    for minutes, cumulative_pnl in trades_pnl:
        timestamp = base_time + timedelta(minutes=minutes)
        equity_points.append(EquityPoint(
            timestamp=timestamp,
            cumulative_pnl=cumulative_pnl
        ))

    # Sample stats for negative day
    chart_stats = ChartStats(
        total_net_pnl=-141.40,
        max_drawdown_percent=18.75,
        max_drawdown_usdt=141.40,
        num_trades=7,
        win_rate=28.57,
        total_used_equity=7000.00,
        profit_factor=0.45,
        win_loss_ratio=0.62,
    )

    return equity_points, chart_stats


if __name__ == "__main__":
    import os
    print("Generating sample equity curves with stats footer...")

    # Get logo path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(script_dir, "logo.jpg")
    print(f"Logo path: {logo_path}")
    print(f"Logo exists: {os.path.exists(logo_path)}")

    # Generate positive day chart
    print("\n1. Generating PROFITABLE day chart...")
    positive_points, positive_stats = create_sample_data_positive()
    positive_chart = generate_equity_curve_image(positive_points, "2026-01-19", positive_stats, logo_path)

    if positive_chart:
        with open("sample_equity_curve_positive.png", "wb") as f:
            f.write(positive_chart.read())
        print("   Saved: sample_equity_curve_positive.png")

    # Generate negative day chart
    print("\n2. Generating LOSING day chart...")
    negative_points, negative_stats = create_sample_data_negative()
    negative_chart = generate_equity_curve_image(negative_points, "2026-01-19", negative_stats, logo_path)

    if negative_chart:
        with open("sample_equity_curve_negative.png", "wb") as f:
            f.write(negative_chart.read())
        print("   Saved: sample_equity_curve_negative.png")

    print("\n" + "="*50)
    print("Done! Check the generated PNG files:")
    print("  - sample_equity_curve_positive.png (green, with stats)")
    print("  - sample_equity_curve_negative.png (red, with stats)")
    print("="*50)

    print("\nStats included in footer:")
    print("  - Total Net PnL (USDT)")
    print("  - Max Drawdown (%)")
    print("  - Number of Trades")
    print("  - Win Rate (%)")
    print("  - Total Used Equity (USDT)")
    print("  - Max Drawdown (USDT)")
    print("  - Profit Factor")
    print("  - Win / Loss Ratio")
