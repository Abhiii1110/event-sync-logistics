from rest_framework import serializers
from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    # Only CLIENT or VENDOR can self-register. Nobody can sign up as ADMIN.
    role = serializers.ChoiceField(choices=["CLIENT", "VENDOR"])

    class Meta:
        model = User
        fields = ("id", "username", "email", "password", "role", "phone")

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)  # hashes the password


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "role", "phone")