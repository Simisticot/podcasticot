document.querySelector("body").addEventListener('click', function(event) {
	if (event.target.tagName.toLowerCase() === "h2") {
		let container = event.target.parentElement.parentElement;
		if (container.classList.contains("unexpanded")) {
			container.classList.remove("unexpanded");
			container.classList.add("expanded");
		}
		else {

			container.classList.remove("expanded");
			container.classList.add("unexpanded");
		}

	}
});
