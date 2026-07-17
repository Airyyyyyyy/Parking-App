"""
Generate report figures for the Model Evaluation chapter.

Usage:
    python manage.py make_charts

Saves PNG images into the project's `report_charts/` folder, ready to drop
into the write-up:

  * figure_4_1_class_distribution.png  – bar chart of the number of training
    records in each availability class (High / Medium / Low).
  * figure_4_2_confusion_matrix.png    – the Decision Tree's confusion matrix
    on the held-out test set.
"""
from pathlib import Path

import matplotlib
matplotlib.use('Agg')  # no GUI / headless — just write files
import matplotlib.pyplot as plt

from django.conf import settings
from django.core.management.base import BaseCommand

from parking.models import OccupancyRecord
from analytics.ml_engine import ParkingMLEngine

# Availability class order and colours (match the app's High/Medium/Low scheme)
CLASSES = ['High', 'Medium', 'Low']
COLOURS = {'High': '#388e3c', 'Medium': '#f57c00', 'Low': '#d32f2f'}


class Command(BaseCommand):
    help = 'Generate PNG report figures (class distribution, confusion matrix).'

    def handle(self, *args, **kwargs):
        out_dir = Path(settings.BASE_DIR) / 'report_charts'
        out_dir.mkdir(exist_ok=True)

        records = list(OccupancyRecord.objects.values_list('occupancy_percentage', flat=True))
        if not records:
            self.stdout.write(self.style.WARNING(
                'No occupancy records found. Run "python manage.py seed_data" first.'))
            return

        self._figure_class_distribution(records, out_dir)
        self._figure_confusion_matrix(out_dir)

        self.stdout.write(self.style.SUCCESS(f'\nFigures saved to: {out_dir}\n'))

    # ── Figure 4.1: class distribution ─────────────────────────────────────
    def _figure_class_distribution(self, records, out_dir):
        counts = {c: 0 for c in CLASSES}
        for pct in records:
            counts[ParkingMLEngine._classify(pct)] += 1

        fig, ax = plt.subplots(figsize=(7, 4.5))
        bars = ax.bar(CLASSES, [counts[c] for c in CLASSES],
                      color=[COLOURS[c] for c in CLASSES], width=0.6)

        ax.set_title('Availability Class Distribution in the Training Data',
                     fontsize=13, fontweight='bold', pad=14)
        ax.set_xlabel('Availability class', fontsize=11)
        ax.set_ylabel('Number of occupancy records', fontsize=11)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(axis='y', linestyle='--', alpha=0.4)

        for bar, c in zip(bars, CLASSES):
            ax.annotate(f'{counts[c]:,}',
                        xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                        xytext=(0, 4), textcoords='offset points',
                        ha='center', va='bottom', fontsize=11, fontweight='bold')

        fig.tight_layout()
        path = out_dir / 'figure_4_1_class_distribution.png'
        fig.savefig(path, dpi=150)
        plt.close(fig)

        total = sum(counts.values())
        self.stdout.write(self.style.SUCCESS(f'Figure 4.1 -> {path.name}'))
        for c in CLASSES:
            pct = (counts[c] / total * 100) if total else 0
            self.stdout.write(f'   {c:<7}: {counts[c]:>6,}  ({pct:.1f}%)')

    # ── Figure 4.2: confusion matrix ───────────────────────────────────────
    def _figure_confusion_matrix(self, out_dir):
        metrics = ParkingMLEngine().get_metrics()['decision_tree']
        if not metrics:
            self.stdout.write(self.style.WARNING(
                'Skipping confusion matrix — not enough data to evaluate the model.'))
            return

        labels = metrics['labels']
        matrix = metrics['confusion']

        fig, ax = plt.subplots(figsize=(5.5, 5))
        im = ax.imshow(matrix, cmap='Oranges')

        ax.set_xticks(range(len(labels)), labels=labels)
        ax.set_yticks(range(len(labels)), labels=labels)
        ax.set_xlabel('Predicted class', fontsize=11)
        ax.set_ylabel('Actual class', fontsize=11)
        ax.set_title(f"Decision Tree Confusion Matrix\n(Test accuracy: {metrics['accuracy']}%)",
                     fontsize=12, fontweight='bold', pad=14)

        # Annotate each cell; pick readable text colour based on cell value.
        vmax = max((max(row) for row in matrix), default=0)
        for i, row in enumerate(matrix):
            for j, val in enumerate(row):
                colour = 'white' if val > vmax * 0.6 else '#1e293b'
                ax.text(j, i, str(val), ha='center', va='center',
                        color=colour, fontsize=12, fontweight='bold')

        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
        fig.tight_layout()
        path = out_dir / 'figure_4_2_confusion_matrix.png'
        fig.savefig(path, dpi=150)
        plt.close(fig)

        self.stdout.write(self.style.SUCCESS(f'Figure 4.2 -> {path.name}'))
