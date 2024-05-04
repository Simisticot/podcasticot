function update_current_time() {
	player_control = document.getElementById("player-control");
	episode_id = player_control.getAttribute("data-episode-id")
	seconds = Math.trunc(player_control.currentTime)
	fetch("current-time/" + episode_id + "/" + seconds, { method: "POST" });
}

document.getElementById("update-button").addEventListener("click", update_current_time);
