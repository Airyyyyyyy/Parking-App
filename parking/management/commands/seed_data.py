from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import random

from accounts.models import CustomUser
from parking.models import ParkingLot, ParkingSlot, OccupancyRecord

HOUR_WEIGHTS = [
    10,10,10,10,10,15,
    30,55,75,85,80,70,
    65,70,75,80,85,80,
    60,45,35,25,15,10,
]

class Command(BaseCommand):
    help = 'Seed the database with realistic sample parking data'

    def handle(self, *args, **kwargs):
        # ── Admin user ───────────────────────────────────────────────────
        # Login is by phone number, so the admin MUST have one set.
        ADMIN_PHONE = '08000000000'
        admin = CustomUser.objects.filter(username='admin').first()
        if admin is None:
            admin = CustomUser.objects.create_superuser(
                username='admin',
                email='admin@parking.ng',
                password='Admin@2025',
                role='admin',
                phone_number=ADMIN_PHONE,
            )
            self.stdout.write('Created admin user')
        else:
            # Backfill the phone number on an existing admin so login works.
            if not admin.phone_number:
                admin.phone_number = ADMIN_PHONE
                admin.save()
            self.stdout.write('Admin user already exists')
        self.stdout.write(f'  Admin login  -> phone: {ADMIN_PHONE}  password: Admin@2025')

        # ── Sample lots ──────────────────────────────────────────────────
        LOTS = [
            {'name': 'Boys Hostel Car Park',
             'address': 'Main Entrance, Chrisland University, Owode Egba, Ogun State',
             'lat': 6.9940, 'lng': 3.2490, 'slots': 30},
            {'name': 'Admin Car Park',
             'address': 'Academic Block, Chrisland University, Owode Egba, Ogun State',
             'lat': 6.9955, 'lng': 3.2505, 'slots': 40},
            {'name': 'Girls Hostel Parking',
             'address': 'Hostel Complex, Chrisland University, Owode Egba, Ogun State',
             'lat': 6.9928, 'lng': 3.2478, 'slots': 50},
            { 'name': 'Clinic Car Park',
            'address': 'Health Services, Chrisland University, Owode Egba, Ogun State',
            'lat': 6.9935, 'lng': 3.2485, 'slots': 25},
        ]

        for ld in LOTS:
            lot = ParkingLot.objects.filter(name=ld['name']).first()
            if lot is None:
                lot = ParkingLot.objects.create(
                    name=ld['name'],
                    address=ld['address'],
                    latitude=ld['lat'],
                    longitude=ld['lng'],
                    total_slots=ld['slots'],
                    available_slots=ld['slots'],
                    admin=admin,
                )
                self.stdout.write(f"Created lot: {lot.name}")
            else:
                self.stdout.write(f"Lot already exists: {lot.name}")

            # ── Parking slots ────────────────────────────────────────────
            existing_slots = ParkingSlot.objects.filter(lot=lot).first()
            if existing_slots is None:
                slots = [
                    ParkingSlot(lot=lot, slot_number=f"S{i:03d}", status='available')
                    for i in range(1, ld['slots'] + 1)
                ]
                ParkingSlot.objects.bulk_create(slots)
                self.stdout.write(f"  Created {ld['slots']} slots")

            # ── Occupancy records (60 days × 24 hours) ───────────────────
            existing_records = OccupancyRecord.objects.filter(lot=lot).first()
            if existing_records is not None:
                self.stdout.write(f"  Records already exist for {lot.name}, skipping")
                continue

            records = []
            for days_back in range(60, 0, -1):
                dt = timezone.now() - timedelta(days=days_back)
                is_weekend = dt.weekday() >= 5
                is_friday  = dt.weekday() == 4

                for hour in range(24):
                    base   = HOUR_WEIGHTS[hour]
                    noise  = random.uniform(-8, 8)
                    factor = 1.15 if is_friday else (0.65 if is_weekend else 1.0)
                    occ    = min(98, max(5, (base + noise) * factor))

                    records.append(OccupancyRecord(
                        lot=lot,
                        recorded_at=dt.replace(hour=hour, minute=0, second=0, microsecond=0),
                        occupancy_percentage=occ,
                        day_of_week=dt.weekday(),
                        hour_of_day=hour,
                        is_weekend=is_weekend,
                    ))

            OccupancyRecord.objects.bulk_create(records)
            self.stdout.write(f"  Created {len(records)} occupancy records")

        self.stdout.write(self.style.SUCCESS('Seeding complete.'))
