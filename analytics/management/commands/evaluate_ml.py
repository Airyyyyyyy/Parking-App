"""
Evaluate the Decision Tree model and print a report.

Usage:
    python manage.py evaluate_ml

Prints the Decision Tree's held-out test accuracy, confusion matrix (over the
Low / Medium / High availability classes) and per-class precision/recall/F1.
Designed to be screenshotted for the project report's "Model Evaluation" section.
"""
from django.core.management.base import BaseCommand
from analytics.ml_engine import ParkingMLEngine

LINE = "=" * 58


class Command(BaseCommand):
    help = 'Evaluate the Decision Tree availability classifier and print metrics.'

    def handle(self, *args, **kwargs):
        engine = ParkingMLEngine()
        dt = engine.get_metrics()['decision_tree']

        self.stdout.write(self.style.MIGRATE_HEADING(f"\n{LINE}"))
        self.stdout.write(self.style.MIGRATE_HEADING(
            "  DECISION TREE - Availability Classifier (High/Medium/Low)"))
        self.stdout.write(self.style.MIGRATE_HEADING(LINE))

        if not dt:
            self.stdout.write(self.style.WARNING(
                'No Decision Tree metrics. Run "python manage.py seed_data" '
                'first to generate training data.'))
            return

        self.stdout.write(
            f"\n   Features         : parking lot, day of week, hour, weekend")
        self.stdout.write(
            f"   Train/Test split : {dt['n_train']} train / {dt['n_test']} test")
        self.stdout.write(self.style.SUCCESS(
            f"   Test accuracy    : {dt['accuracy']}%"))

        # Confusion matrix
        labels = dt['labels']
        self.stdout.write("\n   Confusion matrix (rows=actual, cols=predicted):")
        header = "          " + "".join(f"{lab[:9]:>11}" for lab in labels)
        self.stdout.write(header)
        for lab, row in zip(labels, dt['confusion']):
            cells = "".join(f"{v:>11}" for v in row)
            self.stdout.write(f"   {lab[:8]:>8} {cells}")

        # Per-class report
        self.stdout.write("\n   Classification report:")
        for line in dt['report'].splitlines():
            self.stdout.write(f"      {line}")

        self.stdout.write(self.style.SUCCESS('\nEvaluation complete.\n'))
