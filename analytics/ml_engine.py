import pandas as pd
from datetime import datetime
from sklearn.tree import DecisionTreeClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report
from parking.models import OccupancyRecord, ParkingLot


class ParkingMLEngine:
    FEATURES = ['lot_id', 'day_of_week', 'hour_of_day', 'is_weekend']
    CLASS_ORDER = ['Low', 'Medium', 'High']  

    def __init__(self):
        self.model    = None    
        self.metrics  = {}      
        self._trained = False

    def _ensure_trained(self):
        if not self._trained:
            self._trained = True
            self._train_all()

    # ── Training ───────────────────────────────────────────────────────────
    def _train_all(self):
        raw = list(OccupancyRecord.objects.values(
            'lot_id', 'day_of_week', 'hour_of_day', 'is_weekend', 'occupancy_percentage'
        ))
        if len(raw) < 10:
            return

        df = pd.DataFrame(raw)
        df['label'] = df['occupancy_percentage'].apply(self._classify)

        X = df[self.FEATURES].astype(int)
        y = df['label']

        self._train_and_evaluate(X, y)

    def _train_and_evaluate(self, X, y):
        """
        Hold out 25% of the records as a test set, evaluate the tree on it
        (accuracy + confusion matrix + per-class report), then refit on the full
        dataset for live predictions.
        """
        classes = sorted(y.unique().tolist())

        # Only split when we have enough data and at least two classes present.
        if len(X) >= 20 and len(classes) >= 2:
            # Stratify to keep class balance in train/test when feasible.
            stratify = y if y.value_counts().min() >= 2 else None
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.25, random_state=42, stratify=stratify
            )

            eval_model = DecisionTreeClassifier(
                max_depth=6, min_samples_split=5, random_state=42
            )
            eval_model.fit(X_train, y_train)
            y_pred = eval_model.predict(X_test)

            # Present labels in the natural Low -> Medium -> High order.
            labels_present = [c for c in self.CLASS_ORDER if c in set(y_test) | set(y_pred)]
            self.metrics = {
                'accuracy':  round(accuracy_score(y_test, y_pred) * 100, 1),
                'labels':    labels_present,
                'confusion': confusion_matrix(y_test, y_pred, labels=labels_present).tolist(),
                'report':    classification_report(
                    y_test, y_pred, labels=labels_present, zero_division=0
                ),
                'n_train':   len(X_train),
                'n_test':    len(X_test),
            }

        # Refit on all available data for the model that serves predictions.
        model = DecisionTreeClassifier(
            max_depth=6, min_samples_split=5, random_state=42
        )
        model.fit(X, y)
        self.model = model

    # ── Predict current availability ───────────────────────────────────────
    def predict_availability(self, lot_id: int) -> dict:
        self._ensure_trained()
        if self.model is None:
            return {'class': 'Unknown', 'confidence': 0.0, 'colour': '#9e9e9e'}

        now      = datetime.now()
        features = [[lot_id, now.weekday(), now.hour, int(now.weekday() >= 5)]]
        pred     = self.model.predict(features)[0]
        conf     = float(self.model.predict_proba(features).max())

        return {
            'class':      pred,
            'confidence': round(conf * 100),
            'colour':     self._avail_colour(pred),
        }

    # ── Evaluation metrics (for reporting) ─────────────────────────────────
    def get_metrics(self) -> dict:
        """
        Return the stored Decision Tree evaluation metrics, training if needed.
          {'decision_tree': {accuracy, labels, confusion, report, n_train, n_test}}
        """
        self._ensure_trained()
        return {'decision_tree': self.metrics}

    # ── Hourly average occupancy (for bar chart) ───────────────────────────
    def hourly_averages(self, lot_id: int) -> dict:
        self._ensure_trained()
        raw = list(OccupancyRecord.objects.filter(lot_id=lot_id).values(
            'hour_of_day', 'occupancy_percentage'
        ))
        if not raw:
            return {'labels': list(range(24)), 'values': [0] * 24, 'colours': ['#9e9e9e'] * 24}

        df   = pd.DataFrame(raw)
        avgs = df.groupby('hour_of_day')['occupancy_percentage'].mean()

        values  = [round(float(avgs.get(h, 0)), 1) for h in range(24)]
        colours = [self._occ_colour(v) for v in values]
        return {'labels': list(range(24)), 'values': values, 'colours': colours}

    # ── Recommendations ────────────────────────────────────────────────────
    def get_recommendations(self, lot_id: int) -> dict:
        self._ensure_trained()
        raw = list(OccupancyRecord.objects.filter(lot_id=lot_id).values(
            'hour_of_day', 'occupancy_percentage', 'is_weekend'
        ))
        if not raw:
            return {
                'best_str':    'Not enough data yet',
                'worst_str':   'Not enough data yet',
                'campus_note': 'Seed the database to enable recommendations.',
                'peak_hour_str': 'N/A',
            }

        df         = pd.DataFrame(raw)
        weekday_df = df[~df['is_weekend']]
        source     = weekday_df if len(weekday_df) > 0 else df
        hourly     = source.groupby('hour_of_day')['occupancy_percentage'].mean()

        best_hours  = hourly.nsmallest(3).index.tolist()
        worst_hours = hourly.nlargest(3).index.tolist()

        school_range = list(range(8, 18))
        school_vals  = hourly[hourly.index.isin(school_range)]
        school_avg   = float(school_vals.mean()) if len(school_vals) > 0 else 0.0

        if school_avg >= 70:
            campus_note = "Very busy during school hours (8am–5pm). Arrive before 8am or after 5pm for the best chance of finding a space."
        elif school_avg >= 45:
            campus_note = "Moderately busy during school hours (8am–5pm). Try arriving before 8am to beat the rush."
        else:
            campus_note = "Generally available even during school hours — a good campus option."

        return {
            'best_str':      ', '.join(self._fmt_hour(h) for h in sorted(best_hours)),
            'worst_str':     ', '.join(self._fmt_hour(h) for h in sorted(worst_hours)),
            'campus_note':   campus_note,
            'peak_hour_str': self._fmt_hour(int(hourly.idxmax())),
        }

    # ── Helpers ───────────────────────────────────────────────────────────
    @staticmethod
    def _classify(pct: float) -> str:
        """Map occupancy percentage to an availability class (inverse of occupancy)."""
        if pct >= 70: return 'Low'      # busy lot -> low availability
        if pct >= 35: return 'Medium'
        return 'High'                   # empty lot -> high availability

    @staticmethod
    def _avail_colour(label: str) -> str:
        return {'High': '#388e3c', 'Medium': '#f57c00', 'Low': '#d32f2f'}.get(label, '#9e9e9e')

    @staticmethod
    def _occ_colour(pct: float) -> str:
        if pct >= 70: return '#d32f2f'
        if pct >= 35: return '#f57c00'
        return '#388e3c'

    @staticmethod
    def _fmt_hour(h: int) -> str:
        if h == 0:  return '12am'
        if h < 12:  return f'{h}am'
        if h == 12: return '12pm'
        return f'{h - 12}pm'
