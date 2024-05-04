function update_current_time() {
	player_control = document.getElementById("player-control");
	if( player_control != null && !player_control.paused ){
		episode_id = player_control.getAttribute("data-episode-id");
		seconds = Math.trunc(player_control.currentTime);
		fetch("current-time/" + episode_id + "/" + seconds, { method: "POST" });
	}
}


window.onload = function() {
	setInterval(update_current_time, 5000);
}
