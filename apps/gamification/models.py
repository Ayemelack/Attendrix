from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.institutions.models import Institution

User = get_user_model()


class Badge(models.Model):
    """Achievement badges"""
    RARITY_CHOICES = [
        ('common', 'Common'),
        ('uncommon', 'Uncommon'),
        ('rare', 'Rare'),
        ('epic', 'Epic'),
        ('legendary', 'Legendary'),
    ]
    
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=50, help_text="Icon class or emoji")
    rarity = models.CharField(max_length=20, choices=RARITY_CHOICES, default='common')
    points = models.PositiveIntegerField(default=10)
    unlock_condition = models.JSONField(help_text="Conditions to unlock this badge")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Badge'
        verbose_name_plural = 'Badges'
    
    def __str__(self):
        return f"{self.name} ({self.rarity})"


class UserBadge(models.Model):
    """User earned badges"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='badges')
    badge = models.ForeignKey(Badge, on_delete=models.CASCADE, related_name='user_badges')
    earned_at = models.DateTimeField(auto_now_add=True)
    progress = models.JSONField(default=dict, help_text="Progress towards earning the badge")
    
    class Meta:
        verbose_name = 'User Badge'
        verbose_name_plural = 'User Badges'
        unique_together = ['user', 'badge']
    
    def __str__(self):
        return f"{self.user.username} - {self.badge.name}"


class Leaderboard(models.Model):
    """Leaderboard configurations"""
    name = models.CharField(max_length=100)
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='leaderboards')
    metric = models.CharField(max_length=50, choices=[
        ('attendance_rate', 'Attendance Rate'),
        ('points', 'Total Points'),
        ('streak_days', 'Streak Days'),
        ('badges_count', 'Badges Count'),
    ])
    period = models.CharField(max_length=20, choices=[
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('all_time', 'All Time'),
    ], default='monthly')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Leaderboard'
        verbose_name_plural = 'Leaderboards'
        unique_together = ['name', 'institution', 'metric', 'period']
    
    def __str__(self):
        return f"{self.name} - {self.institution.name}"


class LeaderboardEntry(models.Model):
    """Leaderboard entries"""
    leaderboard = models.ForeignKey(Leaderboard, on_delete=models.CASCADE, related_name='entries')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leaderboard_entries')
    score = models.DecimalField(max_digits=10, decimal_places=2)
    rank = models.PositiveIntegerField()
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Leaderboard Entry'
        verbose_name_plural = 'Leaderboard Entries'
        unique_together = ['leaderboard', 'user']
        ordering = ['rank']
    
    def __str__(self):
        return f"#{self.rank} {self.user.username} - {self.score}"


class Achievement(models.Model):
    """Achievement milestones"""
    title = models.CharField(max_length=100)
    description = models.TextField()
    points = models.PositiveIntegerField(default=50)
    category = models.CharField(max_length=50, choices=[
        ('attendance', 'Attendance'),
        ('academic', 'Academic'),
        ('social', 'Social'),
        ('leadership', 'Leadership'),
        ('custom', 'Custom'),
    ])
    unlock_conditions = models.JSONField(help_text="Conditions to unlock this achievement")
    reward_badge = models.ForeignKey(Badge, on_delete=models.SET_NULL, null=True, blank=True, related_name='achievement_rewards')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Achievement'
        verbose_name_plural = 'Achievements'
    
    def __str__(self):
        return f"{self.title} ({self.category})"


class UserAchievement(models.Model):
    """User earned achievements"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='achievements')
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE, related_name='user_achievements')
    earned_at = models.DateTimeField(auto_now_add=True)
    progress = models.JSONField(default=dict)
    
    class Meta:
        verbose_name = 'User Achievement'
        verbose_name_plural = 'User Achievements'
        unique_together = ['user', 'achievement']
    
    def __str__(self):
        return f"{self.user.username} - {self.achievement.title}"


class PointsTransaction(models.Model):
    """Points transactions for users"""
    TRANSACTION_TYPES = [
        ('earned', 'Earned'),
        ('spent', 'Spent'),
        ('bonus', 'Bonus'),
        ('penalty', 'Penalty'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='points_transactions')
    points = models.IntegerField(help_text="Positive for earned, negative for spent")
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    description = models.CharField(max_length=200)
    reference_id = models.CharField(max_length=100, blank=True, help_text="Reference to related object")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Points Transaction'
        verbose_name_plural = 'Points Transactions'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username}: {self.points} points ({self.transaction_type})"


class UserLevel(models.Model):
    """User levels and progression"""
    level = models.PositiveIntegerField(unique=True)
    name = models.CharField(max_length=50)
    min_points = models.PositiveIntegerField()
    max_points = models.PositiveIntegerField()
    rewards = models.JSONField(default=dict, help_text="Rewards for reaching this level")
    icon = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=7, default="#6c757d", help_text="Hex color code")
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'User Level'
        verbose_name_plural = 'User Levels'
        ordering = ['level']
    
    def __str__(self):
        return f"Level {self.level}: {self.name}"


class UserProgress(models.Model):
    """User overall progress"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='progress')
    total_points = models.PositiveIntegerField(default=0)
    current_level = models.ForeignKey(UserLevel, on_delete=models.SET_NULL, null=True, related_name='users')
    level_progress = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Progress towards next level")
    streak_days = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    last_active_date = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'User Progress'
        verbose_name_plural = 'User Progress'
    
    def __str__(self):
        return f"{self.user.username} - Level {self.current_level.level if self.current_level else 0}"
    
    def update_level(self):
        """Update user level based on total points"""
        if self.current_level:
            next_level = UserLevel.objects.filter(
                level__gt=self.current_level.level,
                min_points__lte=self.total_points
            ).order_by('level').first()
            
            if next_level:
                self.current_level = next_level
                self.level_progress = ((self.total_points - next_level.min_points) / 
                                     (next_level.max_points - next_level.min_points)) * 100
            else:
                # Check if user should be at a higher level
                higher_level = UserLevel.objects.filter(
                    min_points__lte=self.total_points
                ).order_by('-level').first()
                if higher_level and higher_level.level > self.current_level.level:
                    self.current_level = higher_level
                    self.level_progress = 0
        else:
            # Find initial level
            level = UserLevel.objects.filter(
                min_points__lte=self.total_points
            ).order_by('-level').first()
            self.current_level = level
            self.level_progress = 0 if level else 0
        
        self.save()


class Streak(models.Model):
    """User streaks for various activities"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='streaks')
    streak_type = models.CharField(max_length=50, choices=[
        ('attendance', 'Attendance'),
        ('login', 'Login'),
        ('study', 'Study'),
    ])
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    last_activity_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Streak'
        verbose_name_plural = 'Streaks'
        unique_together = ['user', 'streak_type']
    
    def __str__(self):
        return f"{self.user.username} - {self.streak_type} ({self.current_streak} days)"


class Challenge(models.Model):
    """Challenges for users to complete"""
    title = models.CharField(max_length=100)
    description = models.TextField()
    institution = models.ForeignKey(Institution, on_delete=models.CASCADE, related_name='challenges', null=True, blank=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    points_reward = models.PositiveIntegerField(default=100)
    badge_reward = models.ForeignKey(Badge, on_delete=models.SET_NULL, null=True, blank=True, related_name='challenge_rewards')
    participation_limit = models.PositiveIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Challenge'
        verbose_name_plural = 'Challenges'
    
    def __str__(self):
        return f"{self.title} ({self.points_reward} points)"


class UserChallenge(models.Model):
    """User participation in challenges"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='challenges')
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name='participants')
    joined_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    progress = models.JSONField(default=dict)
    is_completed = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = 'User Challenge'
        verbose_name_plural = 'User Challenges'
        unique_together = ['user', 'challenge']
    
    def __str__(self):
        return f"{self.user.username} - {self.challenge.title}"
