#!/usr/bin/env bash
set -u

# Read-only machine connectivity probe; it may contact the supplied endpoints but changes no service state.

: "${TEMI_IP:?Set TEMI_IP to the Temi robot address.}"
: "${PC_IP:?Set PC_IP to the MQTT/video host address.}"

echo "== Local PC network =="
ip -br addr
ip route

echo
echo "== Local service ports =="
ss -ltnp | grep -E ':1883|:8080|:8081|:5037' || true

echo
echo "== Temi TCP probes =="
nc -vz -w 3 "$TEMI_IP" 5555
nc -vz -w 3 "$PC_IP" 1883
nc -vz -w 3 "$PC_IP" 8080
nc -vz -w 3 "$PC_IP" 8081

echo
echo "== ADB status =="
adb connect "$TEMI_IP:5555" || true
adb devices -l

echo
echo "== MQTT quick monitor hint =="
echo "Run: timeout 30 mosquitto_sub -h $PC_IP -p 1883 -t '#' -v"
