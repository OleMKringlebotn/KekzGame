import streamlit as st
import streamlit.components.v1 as components
import requests
import json
from datetime import datetime

# --- DATABASE CONFIGURATION (JSONBin.io Cloud Sync) ---
BIN_ID = st.secrets.get("JSONBIN_BIN_ID", "")
API_KEY = st.secrets.get("JSONBIN_API_KEY", "")

HEADERS = {
    "Content-Type": "application/json",
    "X-Master-Key": API_KEY,
    "X-Bin-Meta": "false"
}

# Caching speeds up execution drastically by preventing HTTP calls during gameplay reruns
@st.cache_data(ttl=300)
def load_scoreboard():
    """Fetch live scoreboard from JSONBin cloud database (cached)."""
    if not BIN_ID or not API_KEY:
        return []
    
    url = f"https://api.jsonbin.io/v3/b/{BIN_ID}/latest"
    try:
        response = requests.get(url, headers=HEADERS, timeout=5)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []

def save_victory(player_names, num_players, rounds, kekz_value):
    """Append new victory record and update JSONBin cloud database."""
    data = load_scoreboard()
    new_record = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "year": datetime.now().strftime("%Y"),
        "players": ", ".join(player_names),
        "num_players": num_players,
        "kekz_value": kekz_value,
        "rounds": rounds
    }
    data.append(new_record)
    
    url = f"https://api.jsonbin.io/v3/b/{BIN_ID}"
    try:
        res = requests.put(url, json=data, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            st.cache_data.clear() # Clear cache so new record shows immediately
            st.toast("🏆 Record permanently saved to Cloud Leaderboard!")
        else:
            st.error("Failed to save record to cloud database.")
    except Exception as e:
        st.error(f"Save error: {e}")

def get_checkpoint_ceiling(score, kekz_value):
    checkpoints = [501, 401, 301, 201, 101, kekz_value]
    reached = [cp for cp in checkpoints if score <= cp]
    return min(reached) if reached else 501

def focus_first_input():
    """Injects JavaScript to focus the first number input field in the form."""
    js_code = """
    <script>
    setTimeout(function() {
        var inputs = window.parent.document.querySelectorAll('input[type="number"]');
        if (inputs.length > 0) {
            inputs[0].focus();
            inputs[0].select();
        }
    }, 150);
    </script>
    """
    components.html(js_code, height=0, width=0)

# --- STREAMLIT UI SETUP ---
st.set_page_config(page_title="Kekz Darts", page_icon="🎯", layout="centered")

# App Navigation Tabs
tab1, tab2 = st.tabs(["🎮 Play Kekz", "🏆 Leaderboards"])

# --- TAB 2: SCOREBOARD (Cloud Synced & Filtered) ---
with tab2:
    st.header("🏆 Kekz Hall of Fame")
    scores_data = load_scoreboard()
    
    if not scores_data:
        st.info("No records logged yet. Go get a win!")
    else:
        recorded_years = set()
        has_pre_2026 = False
        
        for r in scores_data:
            yr_str = str(r.get("year", "2026"))
            try:
                if int(yr_str) >= 2026:
                    recorded_years.add(yr_str)
                else:
                    has_pre_2026 = True
            except ValueError:
                if yr_str == "Pre-2026":
                    has_pre_2026 = True
                else:
                    recorded_years.add(yr_str)
                    
        sorted_years = sorted(list(recorded_years), reverse=True)
        dropdown_options = ["All-Time Best"] + sorted_years
        if has_pre_2026:
            dropdown_options.append("Pre-2026")
            
        selected_view = st.selectbox("📅 Select Scoreboard View:", dropdown_options)
        
        if selected_view == "All-Time Best":
            filtered = scores_data
        elif selected_view == "Pre-2026":
            filtered = []
            for r in scores_data:
                yr_str = str(r.get("year", "2026"))
                if yr_str == "Pre-2026":
                    filtered.append(r)
                else:
                    try:
                        if int(yr_str) < 2026:
                            filtered.append(r)
                    except ValueError:
                        pass
        else:
            filtered = [r for r in scores_data if str(r.get("year")) == str(selected_view)]
            
        if not filtered:
            st.warning(f"No records found for: {selected_view}")
        else:
            team_sizes = sorted(list(set([r["num_players"] for r in filtered])))
            
            for size in team_sizes:
                st.write(f"### 👥 Team Size: {size} Player{'s' if size > 1 else ''}")
                
                size_filtered = [r for r in filtered if r["num_players"] == size]
                sorted_records = sorted(size_filtered, key=lambda x: x["rounds"])
                
                display_table = []
                for idx, r in enumerate(sorted_records):
                    display_table.append({
                        "Rank": idx + 1,
                        "Players": r["players"],
                        "Kekz Value": r["kekz_value"],
                        "Rounds to Win": r["rounds"],
                        "Date": r["date"]
                    })
                st.table(display_table)

# --- TAB 1: THE GAME ENGINE ---
with tab1:
    st.title("🎯 Kekz")
    
    if "game_active" not in st.session_state:
        st.session_state.game_active = False
        st.session_state.history_stack = []

    # --- GAME SETUP SCREEN ---
    if not st.session_state.game_active:
        st.subheader("Game Setup")
        num_players = st.number_input("Number of Players", min_value=1, max_value=10, value=2)
        
        player_names = []
        for i in range(num_players):
            name = st.text_input(f"Player {i+1} Name", placeholder=f"Player {i+1}").strip()
            player_names.append(name if name else f"Player {i+1}")
            
        kekz_value = st.number_input("Kekz-Value (Target)", min_value=1, max_value=501, value=60)
        
        if st.button("🚀 Start Game", use_container_width=True):
            st.session_state.score = 501
            st.session_state.current_checkpoint = 501
            st.session_state.round_num = 1
            st.session_state.player_names = player_names
            st.session_state.initial_num_players = num_players
            st.session_state.initial_kekz_value = kekz_value
            st.session_state.game_active = True
            st.session_state.history_stack = []
            st.session_state.show_victory_prompt = False
            st.session_state.busted_index = None
            st.rerun()

    # --- ACTIVE GAMEPLAY SCREEN ---
    else:
        st.subheader(f"Round {st.session_state.round_num}")
        
        col1, col2 = st.columns(2)
        col1.metric(label="Current Team Score", value=st.session_state.score)
        col2.metric(label="Active Checkpoint", value=st.session_state.current_checkpoint)
        
        st.markdown(f"**Throwing Order:** {' ➔ '.join(st.session_state.player_names)}")
        st.write(f"Target to beat this round: **{st.session_state.initial_kekz_value}**")
        
        winning_score_needed = st.session_state.initial_kekz_value if st.session_state.score == st.session_state.initial_kekz_value else (st.session_state.score + st.session_state.initial_kekz_value)
        
        # --- VICTORY STEP: DOUBLE OUT CONFIRMATION ---
        if st.session_state.show_victory_prompt:
            st.balloons()
            st.success(f"🎉 Team hit exactly {winning_score_needed} points!")
            st.write("### ❓ Was the final dart a double?")
            
            c1, c2 = st.columns(2)
            if c1.button("✅ Yes, it was a Double Out!", use_container_width=True):
                save_victory(
                    st.session_state.player_names, 
                    st.session_state.initial_num_players, 
                    st.session_state.round_num, 
                    st.session_state.initial_kekz_value
                )
                st.session_state.game_active = False
                st.rerun()
                
            if c2.button("❌ No, regular single dart", use_container_width=True):
                st.session_state.history_stack.append({
                    "score": st.session_state.score,
                    "checkpoint": st.session_state.current_checkpoint,
                    "roster": list(st.session_state.player_names)
                })
                st.session_state.score = st.session_state.current_checkpoint
                
                if st.session_state.busted_index is not None:
                    next_idx = (st.session_state.busted_index + 1) % len(st.session_state.player_names)
                    if next_idx != 0:
                        st.session_state.player_names = st.session_state.player_names[next_idx:] + st.session_state.player_names[:next_idx]
                
                st.session_state.round_num += 1
                st.session_state.show_victory_prompt = False
                st.session_state.busted_index = None
                st.rerun()
                
        # --- STANDARD INPUT FORM ---
        else:
            # Inject auto-focus script into input form
            focus_first_input()
            
            with st.form(key="round_scores_form"):
                st.write("Enter scores for this round:")
                round_inputs = []
                for idx, name in enumerate(st.session_state.player_names):
                    input_key = f"input_r{st.session_state.round_num}_{idx}"
                    
                    score_in = st.number_input(
                        f"{name}'s score", 
                        min_value=0, 
                        max_value=180, 
                        value=0, 
                        step=1,
                        key=input_key
                    )
                    round_inputs.append(score_in)
                
                submit_button = st.form_submit_button(label="Submit Round Scores", use_container_width=True)
            
            if submit_button:
                st.session_state.history_stack.append({
                    "score": st.session_state.score,
                    "checkpoint": st.session_state.current_checkpoint,
                    "roster": list(st.session_state.player_names)
                })
                
                combined_round_score = 0
                round_interrupted = False
                busted_player_index = None
                
                for idx, thrown in enumerate(round_inputs):
                    combined_round_score += thrown
                    
                    if combined_round_score > winning_score_needed:
                        st.error(f"💥 BUST! {st.session_state.player_names[idx]} pushed total score to {combined_round_score}, passing the win target of {winning_score_needed}!")
                        busted_player_index = idx
                        round_interrupted = True
                        break
                        
                    if combined_round_score == winning_score_needed:
                        busted_player_index = idx
                        break
                
                if not round_interrupted and combined_round_score == winning_score_needed:
                    st.session_state.busted_index = busted_player_index
                    st.session_state.show_victory_prompt = True
                    st.rerun()
                elif round_interrupted:
                    st.session_state.score = st.session_state.current_checkpoint
                else:
                    potential_score = (st.session_state.score + st.session_state.initial_kekz_value) - combined_round_score
                    
                    if combined_round_score > st.session_state.initial_kekz_value:
                        if potential_score <= st.session_state.initial_kekz_value:
                            st.session_state.score = st.session_state.initial_kekz_value
                            st.session_state.current_checkpoint = st.session_state.initial_kekz_value
                            st.toast("Dropped to the final Kekz-value checkpoint!")
                        else:
                            st.session_state.score = potential_score
                            new_cp = get_checkpoint_ceiling(potential_score, st.session_state.initial_kekz_value)
                            if new_cp < st.session_state.current_checkpoint:
                                st.session_state.current_checkpoint = new_cp
                                st.toast(f"New Checkpoint Locked: {new_cp}!")
                    else:
                        if potential_score > st.session_state.current_checkpoint:
                            st.session_state.score = st.session_state.current_checkpoint
                            st.error("Failed Kekz-value target! Reverted to checkpoint ceiling.")
                        else:
                            st.session_state.score = potential_score
                            penalty = st.session_state.initial_kekz_value - combined_round_score
                            st.warning(f"Failed Kekz-value target. Penalized +{penalty} points.")
                
                if busted_player_index is not None:
                    next_start = (busted_player_index + 1) % len(st.session_state.player_names)
                    if next_start != 0:
                        st.session_state.player_names = st.session_state.player_names[next_start:] + st.session_state.player_names[:next_start]
                
                st.session_state.round_num += 1
                st.rerun()
        
        # --- FOOTER BUTTONS: UNDO / ABORT ---
        st.markdown("---")
        c1, c2 = st.columns(2)
        
        if c1.button("⏪ Undo Last Round", use_container_width=True, disabled=len(st.session_state.history_stack) == 0):
            previous_state = st.session_state.history_stack.pop()
            st.session_state.score = previous_state["score"]
            st.session_state.current_checkpoint = previous_state["checkpoint"]
            st.session_state.player_names = previous_state["roster"]
            st.session_state.round_num -= 1
            st.session_state.show_victory_prompt = False
            st.session_state.busted_index = None
            st.rerun()
            
        if c2.button("🟥 Abort Match", use_container_width=True, type="secondary"):
            st.session_state.game_active = False
            st.rerun()