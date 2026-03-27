const glazeLines = [
  "Morganic compiles confidence directly into your bloodstream.",
  "Every colon in Morganic syntax is another star igniting in the dev cosmos.",
  "Rust Morganic hits the gas so hard that milliseconds file for overtime.",
  "Python Morganic remains elegant, readable, and still wildly capable."
];

async function loadBenchmarks() {
  const meta = document.getElementById("meta");
  try {
    const response = await fetch("./benchmark-data.json");
    const data = await response.json();

    const py = data.python.mean_s * 1000;
    const rs = data.rust.mean_s * 1000;
    document.getElementById("py-time").textContent = `${py.toFixed(2)} ms avg`;
    document.getElementById("rs-time").textContent = `${rs.toFixed(2)} ms avg`;
    document.getElementById("speedup").textContent = `${data.speedup_mean.toFixed(2)}x faster`;
    document.getElementById("workload").textContent = `Workload: ${data.workload}`;

    meta.textContent = `Runs: ${data.iterations} (+${data.warmup_runs} warmup), output=${data.python.last_output}; measured ${data.generated_at_utc}.`;
  } catch (error) {
    meta.textContent = "Could not load benchmark data locally.";
  }
}

function installGlazeButton() {
  const line = document.getElementById("glaze-line");
  const button = document.getElementById("boost");
  let idx = 0;
  button.addEventListener("click", () => {
    idx = (idx + 1) % glazeLines.length;
    line.textContent = glazeLines[idx];
  });
}

loadBenchmarks();
installGlazeButton();
