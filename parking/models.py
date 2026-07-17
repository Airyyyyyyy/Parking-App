from django.db import models
from django.utils import timezone
from accounts.models import CustomUser
# Create your models here.

class ParkingLot(models.Model):
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=200)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    total_slots = models.IntegerField()
    available_slots = models.IntegerField()
    status = models.CharField(max_length=20, default='open',
    choices=[('open', 'Open'), ('closed', 'Closed'), ('maintenance', 'Maintenance')])
    admin = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def occupancy_percentage(self):
        if self.total_slots == 0:
            return 0
        return ((self.total_slots - self.available_slots) / self.total_slots) * 100
    
    def __str__(self):
        return self.name
    
class ParkingSlot(models.Model):
    SLOT_TYPES = [('regular', 'Regular'), ('disabled', 'Disabled')]
    STATUES = [('available', 'Available'), ('occupied', 'Occupied')]
    lot = models.ForeignKey(ParkingLot, on_delete=models.CASCADE, related_name='slots')
    slot_number = models.CharField(max_length=50)
    slot_type = models.CharField(max_length=20, choices=SLOT_TYPES, default='regular')
    status = models.CharField(max_length=20, choices=STATUES, default='available')

    class Meta:
        unique_together = ('lot', 'slot_number')

    def __str__(self):
        return f"{self.lot.name} - Slot {self.slot_number}"

class Booking(models.Model):
    STATUSES = [('confirmed', 'Confirmed'), ('cancelled', 'Cancelled'), ('completed', 'Completed')]
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='bookings')
    slot = models.ForeignKey(ParkingSlot, on_delete=models.CASCADE, related_name='bookings')
    status = models.CharField(max_length=20, choices=STATUSES, default='confirmed')
    booked_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.slot}"

class OccupancyRecord(models.Model):
    lot = models.ForeignKey(ParkingLot, on_delete=models.CASCADE, related_name='records')
    recorded_at = models.DateTimeField(default=timezone.now, db_index=True)
    occupancy_percentage = models.FloatField()
    day_of_week = models.IntegerField()
    hour_of_day = models.IntegerField()
    is_weekend = models.BooleanField()

    class Meta:
        indexes = [models.Index(fields=['lot', 'recorded_at'])]


