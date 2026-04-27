#!/usr/bin/env bash
# ───────────────────────────────────────────────────────────────
# 🍅 Cross-Distro Pomodoro Timer for Waybar
# Works on any Linux distro with bash + coreutils + notify-send
# ───────────────────────────────────────────────────────────────

STATE_FILE="/tmp/pomodoro.state"
NOTIF_URGENCY="normal"

# ── Default durations (seconds) ──
WORK_DURATION=${POMO_WORK:-1500}    # 25 min
BREAK_DURATION=${POMO_BREAK:-300}   # 5 min
LONG_BREAK_DURATION=${POMO_LONG_BREAK:-900}  # 15 min
SESSIONS_BEFORE_LONG_BREAK=${POMO_SESSIONS:-4}

# ── Helper: Save state ──
save_state() {
    cat > "$STATE_FILE" <<EOF
PHASE=$1
REMAINING=$2
RUNNING=$3
SESSION_COUNT=$4
EOF
}

# ── Helper: Load state ──
load_state() {
    if [[ -f "$STATE_FILE" ]]; then
        # shellcheck disable=SC1090
        source "$STATE_FILE"
    else
        PHASE="idle"
        REMAINING=0
        RUNNING="false"
        SESSION_COUNT=0
    fi
}

# ── Helper: Send notification ──
notify() {
    local title="$1"
    local body="$2"
    local icon="${3:-dialog-information}"
    local sound="${4:-false}"

    # Check if notify-send is available
    if command -v notify-send &>/dev/null; then
        notify-send -u "$NOTIF_URGENCY" -i "$icon" "$title" "$body" 2>/dev/null
    fi

    if [[ "$sound" == "true" ]]; then
        play_sound
    fi
}

# ── Helper: Play sound ──
play_sound() {
    local sound_file="/usr/share/sounds/freedesktop/stereo/alarm-clock-elapsed.oga"
    if [[ ! -f "$sound_file" ]]; then
        sound_file="/usr/share/sounds/freedesktop/stereo/complete.oga"
    fi

    if command -v pw-play &>/dev/null; then
        pw-play "$sound_file" &
    elif command -v canberra-gtk-play &>/dev/null; then
        canberra-gtk-play -f "$sound_file" &
    fi
}

# ── Helper: Format seconds to MM:SS ──
format_time() {
    local total_seconds=$1
    local minutes=$((total_seconds / 60))
    local seconds=$((total_seconds % 60))
    printf "%02d:%02d" "$minutes" "$seconds"
}

# ── Helper: Calculate next deadline ──
get_deadline() {
    local phase="$1"
    local duration
    if [[ "$phase" == "work" ]]; then
        duration=$WORK_DURATION
    elif [[ "$phase" == "break" ]]; then
        duration=$BREAK_DURATION
    elif [[ "$phase" == "long_break" ]]; then
        duration=$LONG_BREAK_DURATION
    else
        duration=0
    fi
    echo $(( $(date +%s) + duration ))
}

# ── Command: Start / Resume ──
cmd_start() {
    load_state

    if [[ "$PHASE" == "idle" ]]; then
        # Fresh start
        PHASE="work"
        REMAINING=$WORK_DURATION
        RUNNING="true"
        DEADLINE=$(get_deadline "work")
        save_state "$PHASE" "$REMAINING" "$RUNNING" "$SESSION_COUNT"
        save_deadline "$DEADLINE"
        notify "🍅 Pomodoro Started" "Work session started (25 min)" "view-refresh"
    elif [[ "$PHASE" == "work" || "$PHASE" == "break" || "$PHASE" == "long_break" ]]; then
        if [[ "$RUNNING" == "false" ]]; then
            # Resume from pause
            RUNNING="true"
            # Recalculate deadline based on remaining time
            DEADLINE=$(( $(date +%s) + REMAINING ))
            save_state "$PHASE" "$REMAINING" "$RUNNING" "$SESSION_COUNT"
            save_deadline "$DEADLINE"
            notify "🍅 Resumed" "${PHASE^} session resumed" "view-refresh"
        fi
        # If already running, do nothing
    fi
}

# ── Helper: Save deadline ──
save_deadline() {
    local deadline="$1"
    local temp_file="${STATE_FILE}.tmp"
    
    # Remove old DEADLINE line and add new one
    grep -v "^DEADLINE=" "$STATE_FILE" > "$temp_file" 2>/dev/null
    echo "DEADLINE=$deadline" >> "$temp_file"
    mv "$temp_file" "$STATE_FILE"
}

# ── Command: Pause ──
cmd_pause() {
    load_state

    if [[ "$RUNNING" == "true" ]]; then
        RUNNING="false"
        # Recalculate remaining time from deadline
        local deadline
        deadline=$(grep "^DEADLINE=" "$STATE_FILE" 2>/dev/null | head -1 | cut -d= -f2)
        if [[ -n "$deadline" ]]; then
            REMAINING=$(( deadline - $(date +%s) ))
            if [[ $REMAINING -lt 0 ]]; then
                REMAINING=0
            fi
        fi
        save_state "$PHASE" "$REMAINING" "$RUNNING" "$SESSION_COUNT"
        notify "🍅 Paused" "${PHASE^} session paused" "media-playback-pause"
    fi
}

# ── Command: Reset ──
cmd_reset() {
    rm -f "$STATE_FILE"
    notify "🍅 Reset" "Pomodoro timer reset" "edit-clear"
}

# ── Command: Toggle (start/pause) ──
cmd_toggle() {
    load_state
    if [[ "$RUNNING" == "true" ]]; then
        cmd_pause
    else
        cmd_start
    fi
}

# ── Command: Status (for Waybar output) ──
cmd_status() {
    load_state

    # Check if timer expired and advance phase
    if [[ "$RUNNING" == "true" && "$PHASE" != "idle" ]]; then
        local deadline
        deadline=$(grep "^DEADLINE=" "$STATE_FILE" 2>/dev/null | head -1 | cut -d= -f2)

        if [[ -n "$deadline" ]]; then
            local now
            now=$(date +%s)
            if (( now >= deadline )); then
                advance_phase
                # Reload state after advance
                load_state
            else
                REMAINING=$(( deadline - now ))
            fi
        fi
    fi

    # Output Waybar format
    if [[ "$PHASE" == "idle" ]]; then
        echo "{\"text\":\"🍅 00:00\",\"class\":\"idle\",\"tooltip\":\"Click to start Pomodoro\"}"
    elif [[ "$PHASE" == "work" ]]; then
        local formatted
        formatted=$(format_time "$REMAINING")
        if [[ "$RUNNING" == "true" ]]; then
            echo "{\"text\":\"🍅 $formatted\",\"class\":\"work\",\"tooltip\":\"Work session - Click to pause\"}"
        else
            echo "{\"text\":\"⏸️ $formatted\",\"class\":\"work-paused\",\"tooltip\":\"Paused - Click to resume\"}"
        fi
    elif [[ "$PHASE" == "break" ]]; then
        local formatted
        formatted=$(format_time "$REMAINING")
        if [[ "$RUNNING" == "true" ]]; then
            echo "{\"text\":\"☕ $formatted\",\"class\":\"break\",\"tooltip\":\"Break time - Click to pause\"}"
        else
            echo "{\"text\":\"⏸️ $formatted\",\"class\":\"break-paused\",\"tooltip\":\"Paused - Click to resume\"}"
        fi
    elif [[ "$PHASE" == "long_break" ]]; then
        local formatted
        formatted=$(format_time "$REMAINING")
        if [[ "$RUNNING" == "true" ]]; then
            echo "{\"text\":\"🌴 $formatted\",\"class\":\"long-break\",\"tooltip\":\"Long break - Click to pause\"}"
        else
            echo "{\"text\":\"⏸️ $formatted\",\"class\":\"long-break-paused\",\"tooltip\":\"Paused - Click to resume\"}"
        fi
    fi
}

# ── Internal: Advance to next phase ──
advance_phase() {
    if [[ "$PHASE" == "work" ]]; then
        SESSION_COUNT=$((SESSION_COUNT + 1))

        if (( SESSION_COUNT % SESSIONS_BEFORE_LONG_BREAK == 0 )); then
            PHASE="long_break"
            REMAINING=$LONG_BREAK_DURATION
            notify "🌴 Long Break!" "Great job! Take a 15 min break." "coffee" "true"
        else
            PHASE="break"
            REMAINING=$BREAK_DURATION
            notify "☕ Break Time!" "Work session done. 5 min break." "coffee" "true"
        fi
    else
        PHASE="work"
        REMAINING=$WORK_DURATION
        notify "🍅 Back to Work!" "Break over. Focus time!" "view-refresh" "true"
    fi

    RUNNING="true"
    DEADLINE=$(get_deadline "$PHASE")
    save_state "$PHASE" "$REMAINING" "$RUNNING" "$SESSION_COUNT"
    save_deadline "$DEADLINE"
}

# ── Main: Command dispatcher ──
case "${1:-status}" in
    start)   cmd_start   ;;
    pause)   cmd_pause   ;;
    resume)  cmd_start   ;;
    reset)   cmd_reset   ;;
    toggle)  cmd_toggle  ;;
    status)  cmd_status  ;;
    *)
        echo "Usage: $0 {start|pause|resume|reset|toggle|status}"
        exit 1
        ;;
esac
