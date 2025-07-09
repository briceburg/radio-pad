const stationGrid = document.getElementById('station-grid');
const nowPlaying = document.getElementById('now-playing');

const stationsUrl = 'https://raw.githubusercontent.com/briceburg/radio-pad/refs/heads/main/src/stations.json';
const broadcastUrl = 'https://radio-pad-v0-broadcast-2609704817.us-central1.run.app/?station=';

async function loadStations() {
  try {
    const response = await fetch(stationsUrl);
    const stations = await response.json();

    let ionRow;
    stations.forEach((station, index) => {
      if (index % 3 === 0) {
        ionRow = document.createElement('ion-row');
        stationGrid.appendChild(ionRow);
      }

      const ionCol = document.createElement('ion-col');
      const ionButton = document.createElement('ion-button');
      ionButton.innerText = station.name;
      ionButton.expand = 'block';
      ionButton.addEventListener('click', () => {
        // Remove color attribute from all buttons
        document.querySelectorAll('ion-button').forEach(btn => {
          btn.removeAttribute('color');
        });
        // Set color attribute to "success" for the clicked button
        ionButton.setAttribute('color', 'success');
        playStation(station.name);
      });

      ionCol.appendChild(ionButton);
      ionRow.appendChild(ionCol);
    });
  } catch (error) {
    console.error('Error loading stations:', error);
  }
}

function playStation(stationName) {
  nowPlaying.innerText = stationName;
  fetch(`${broadcastUrl}${stationName}`)
    .then(response => {
      if (!response.ok) {
        console.error(`Error: Received status ${response.status} from player API`);
      }
    })
    .catch(error => {
      console.error('Fetch error:', error);
    });
}

loadStations();
