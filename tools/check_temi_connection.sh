#!/usr/bin/env bash
set -u

TEMI_IP="${TEMI_IP:-192.168.50.205}"
PC_IP="${PC_IP:-192.168.50.236}"

echo "== Local PC network =="
ip -br addr
ip route

echo
echo "== Local service ports =="
ss -ltnp | grep -E ':1883|:8080|:5037' || true

echo
echo "== Temi TCP probes =="
nc -vz -w 3 "$TEMI_IP" 5555
nc -vz -w 3 "$PC_IP" 1883
nc -vz -w 3 "$PC_IP" 8080

echo
echo "== ADB status =="
adb connect "$TEMI_IP:5555" || true
adb devices -l

echo
echo "== MQTT quick monitor hint =="
echo "Run: timeout 30 mosquitto_sub -h $PC_IP -p 1883 -t '#' -v"
