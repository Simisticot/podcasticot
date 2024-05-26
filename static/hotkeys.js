function toggle_play_pause(event) {
	if(event.key != 'k'){
		return;
	}

	player_control = document.getElementById("player-control");
	
	if( player_control == null){
		return;
	}
	if( player_control.paused ){
		player_control.play();
	} else {
		player_control.pause();
	}
}

document.addEventListener('keydown', toggle_play_pause, false);
