document.body.addEventListener("htmx:afterSwap", (event) => {
	if (event.detail.target.id === "player"){
		player_control = document.getElementById("player-control");
		player_control.play()
	}
});
