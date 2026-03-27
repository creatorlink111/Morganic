function toMs(seconds) {
  return seconds * 1000;
}

function formatMs(value) {
  return `${value.toFixed(2)} ms`;
}

function drawBenchmarkChart(data) {
  const canvas = document.getElementById("bench-chart");
  const context = canvas.getContext("2d");
  if (!context) return;

  const values = [
    { label: "Python mean", value: toMs(data.python.mean_s), color: "#7ec8ff" },
    { label: "Rust mean", value: toMs(data.rust.mean_s), color: "#61f5c8" },
    { label: "Python median", value: toMs(data.python.median_s), color: "#6ea9ff" },
    { label: "Rust median", value: toMs(data.rust.median_s), color: "#53ddb4" }
  ];

  const maxValue = Math.max(...values.map((item) => item.value));
  const padding = 28;
  const chartHeight = canvas.height - padding * 2;
  const barAreaWidth = canvas.width - padding * 2;
  const barGap = 24;
  const barWidth = (barAreaWidth - barGap * (values.length - 1)) / values.length;

  context.clearRect(0, 0, canvas.width, canvas.height);
  context.fillStyle = "#0a1224";
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.strokeStyle = "#ffffff33";
  context.lineWidth = 1;
  context.strokeRect(0.5, 0.5, canvas.width - 1, canvas.height - 1);
  context.font = "14px Inter, Segoe UI, sans-serif";

  values.forEach((item, index) => {
    const ratio = item.value / maxValue;
    const barHeight = ratio * (chartHeight - 24);
    const x = padding + index * (barWidth + barGap);
    const y = canvas.height - padding - barHeight;

    context.fillStyle = item.color;
    context.fillRect(x, y, barWidth, barHeight);

    context.fillStyle = "#dbe7ff";
    context.textAlign = "center";
    context.fillText(formatMs(item.value), x + barWidth / 2, y - 8);
    context.fillText(item.label, x + barWidth / 2, canvas.height - 8);
  });
}

async function loadBenchmarks() {
  const meta = document.getElementById("meta");
  try {
    const response = await fetch("./benchmark-data.json");
    const data = await response.json();

    const py = toMs(data.python.mean_s);
    const rs = toMs(data.rust.mean_s);
    const pyMin = toMs(data.python.min_s);
    const pyMax = toMs(data.python.max_s);
    const rsMin = toMs(data.rust.min_s);
    const rsMax = toMs(data.rust.max_s);
    const medianGap = toMs(data.python.median_s - data.rust.median_s);
    document.getElementById("py-time").textContent = `${formatMs(py)} avg`;
    document.getElementById("rs-time").textContent = `${formatMs(rs)} avg`;
    document.getElementById("speedup").textContent = `${data.speedup_mean.toFixed(2)}x faster`;
    document.getElementById("py-range").textContent = `${formatMs(pyMin)} / ${formatMs(pyMax)}`;
    document.getElementById("rs-range").textContent = `${formatMs(rsMin)} / ${formatMs(rsMax)}`;
    document.getElementById("median-gap").textContent = formatMs(medianGap);
    document.getElementById("workload").textContent = `Workload: ${data.workload}`;
    drawBenchmarkChart(data);

    const measured = new Date(data.generated_at_utc).toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      timeZoneName: "short"
    });
    meta.textContent = `Runs: ${data.iterations} (+${data.warmup_runs} warmup), output=${data.python.last_output}; measured ${measured}.`;
  } catch (error) {
    meta.textContent = "Could not load benchmark data locally.";
  }
}

loadBenchmarks();
