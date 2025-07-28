export function renderStationGrid(stations, stationGrid, onStationClick, stationButtons) {
  stationGrid.innerHTML = "";
  let ionRow;
  stations.forEach((station, index) => {
    if (index % 3 === 0) {
      ionRow = document.createElement("ion-row");
      stationGrid.appendChild(ionRow);
    }
    const ionCol = document.createElement("ion-col");
    const ionButton = document.createElement("ion-button");
    ionButton.innerText = station.name;
    ionButton.expand = "block";
    ionButton.addEventListener("click", () => onStationClick(station.name, ionButton));
    stationButtons[station.name] = ionButton;
    ionCol.appendChild(ionButton);
    ionRow.appendChild(ionCol);
  });
}

export function showStationSkeletons(stationGrid, rows = 3, cols = 3) {
  stationGrid.innerHTML = "";
  for (let i = 0; i < rows; i++) {
    const ionRow = document.createElement("ion-row");
    ionRow.className = "station-placeholder";
    for (let j = 0; j < cols; j++) {
      const ionCol = document.createElement("ion-col");
      const skeleton = document.createElement("ion-skeleton-text");
      skeleton.setAttribute("animated", "");
      ionCol.appendChild(skeleton);
      ionRow.appendChild(ionCol);
    }
    stationGrid.appendChild(ionRow);
  }
}

export function highlightCurrentStation(currentPlayingStation, stationButtons, stopButton, nowPlaying) {
  if (currentPlayingStation && stationButtons[currentPlayingStation]) {
    Object.entries(stationButtons).forEach(([name, btn]) =>
      btn.setAttribute(
        "color",
        name === currentPlayingStation ? "success" : "primary",
      ),
    );
    stopButton.disabled = false;
    nowPlaying.innerText = currentPlayingStation || "...";
  } else {
    Object.values(stationButtons).forEach((btn) =>
      btn.setAttribute("color", "primary"),
    );
    stopButton.disabled = true;
    nowPlaying.innerText = "...";
  }
}