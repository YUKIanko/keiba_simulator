const fileInput = document.getElementById("fileInput");

const raceName = document.getElementById("raceName");
const courseMeta = document.getElementById("courseMeta");
const scenarioComment = document.getElementById("scenarioComment");
const shortMemo = document.getElementById("shortMemo");
const worldlineList = document.getElementById("worldlineList");
const worldlineHint = document.getElementById("worldlineHint");
const horseRows = document.getElementById("horseRows");
const devilText = document.getElementById("devilText");
const courseKey = document.getElementById("courseKey");
const laneTracks = document.getElementById("laneTracks");

fileInput.addEventListener("change", (event) => {
  const file = event.target.files[0];
  if (!file) {
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const data = JSON.parse(reader.result);
      render(data);
    } catch (error) {
      raceName.textContent = "JSONの読み込みに失敗しました";
    }
  };
  reader.readAsText(file, "utf-8");
});

function render(data) {
  raceName.textContent = unwrap(data.RaceName, "Unknown");

  const course = unwrap(data.CourseMeta, {});
  const courseText = [
    unwrap(course.Track, null),
    unwrap(course.Surface, null),
    unwrap(course.DistanceM, null) ? `${unwrap(course.DistanceM, null)}m` : null,
    unwrap(course.Direction, null),
    unwrap(course.Layout, null),
  ]
    .filter(Boolean)
    .join(" / ");
  courseMeta.textContent = courseText || "-";

  scenarioComment.textContent = unwrap(data.ScenarioComment, "-");
  shortMemo.textContent = unwrap(data.ShortMemo, "-");
  devilText.textContent = unwrap(data.DevilSpeak, "-");

  renderCourseMeta(unwrap(data.CourseMeta, {}));
  renderWorldlines(unwrapList(data.Worldlines));
  renderLaneTracks(unwrapList(data.FinalMarks));
  renderHorses(unwrapList(data.FinalMarks));
}

function renderWorldlines(worldlines) {
  worldlineList.innerHTML = "";
  if (!worldlines.length) {
    worldlineList.innerHTML = "<span class=\"pill\">No data</span>";
    worldlineHint.textContent = "ワールドラインなし";
    return;
  }
  worldlineHint.textContent = "ワールドラインを選択できます。";
  worldlines.forEach((line, index) => {
    const pill = document.createElement("span");
    pill.className = "pill";
    const pace = unwrap(line.pace_scenario, "-");
    const shape = unwrap(line.shape, "-");
    const probValue = unwrap(line.probability, null);
    const prob = probValue !== null ? ` (${(probValue * 100).toFixed(0)}%)` : "";
    pill.textContent = `${pace} / ${shape}${prob}`;
    if (index === 0) {
      pill.classList.add("active");
      updateScenario(line);
    }
    pill.addEventListener("click", () => {
      document.querySelectorAll(".pill").forEach((node) => node.classList.remove("active"));
      pill.classList.add("active");
      updateScenario(line);
    });
    worldlineList.appendChild(pill);
  });
}

function updateScenario(line) {
  const traffic = unwrap(line.traffic_mode, null) ? `traffic ${unwrap(line.traffic_mode, "")}` : "";
  worldlineHint.textContent = `Selected: ${unwrap(line.pace_scenario, "-")} / ${unwrap(line.shape, "-")} ${traffic}`.trim();
}

function renderHorses(horses) {
  horseRows.innerHTML = "";
  if (!horses.length) {
    horseRows.innerHTML = '<tr><td colspan="7" class="empty">No data</td></tr>';
    return;
  }
  horses.forEach((horse) => {
    const row = document.createElement("tr");
    row.appendChild(cell(unwrap(horse.No, "-")));
    row.appendChild(cell(`${unwrap(horse.Name, "-")} ${unwrap(horse.Mark, "")}`));
    row.appendChild(cell(unwrap(horse.LapType, "-")));
    row.appendChild(barCell(unwrap(horse.PWin, 0)));
    row.appendChild(barCell(unwrap(horse.PIn3, 0)));
    row.appendChild(barCell(unwrap(horse.TrafficFail, 0)));
    row.appendChild(barCell(unwrap(horse.WideCostFail, 0)));
    horseRows.appendChild(row);
  });
}

function cell(text) {
  const td = document.createElement("td");
  td.textContent = text ?? "-";
  return td;
}

function barCell(value) {
  const td = document.createElement("td");
  const wrapper = document.createElement("div");
  wrapper.className = "bar";
  const span = document.createElement("span");
  const ratio = typeof value === "number" ? Math.min(Math.max(value, 0), 1) : 0;
  span.style.width = `${ratio * 100}%`;
  wrapper.appendChild(span);
  td.appendChild(wrapper);
  return td;
}

function renderCourseMeta(course) {
  courseKey.innerHTML = "";
  if (!course || !course.CourseKey) {
    courseKey.innerHTML = "<span class=\"course-chip\">No course meta</span>";
    return;
  }
  const key = unwrap(course.CourseKey, {});
  const items = [
    `Corner ${unwrap(key.CornerSeverity, "-")}`,
    `Lane ${unwrap(key.LaneChangeDifficulty, "-")}`,
    `Straight ${unwrap(key.StraightOpportunity, "-")}`,
    `Uphill ${unwrap(key.UphillTag, "-")}`,
  ];
  items.forEach((text) => {
    const chip = document.createElement("span");
    chip.className = "course-chip";
    chip.textContent = text;
    courseKey.appendChild(chip);
  });
}

function renderLaneTracks(horses) {
  laneTracks.innerHTML = "";
  if (!horses.length) {
    laneTracks.innerHTML = "<div class=\"lane-row\"><span class=\"horse-chip\">No data</span></div>";
    return;
  }
  const buckets = {
    Front: horses.filter((horse) => unwrap(horse.LapType, "") === "A"),
    Mid: horses.filter((horse) => unwrap(horse.LapType, "") === "B"),
    Back: horses.filter((horse) => unwrap(horse.LapType, "") === "C"),
  };
  Object.entries(buckets).forEach(([label, list]) => {
    const row = document.createElement("div");
    row.className = "lane-row";
    const title = document.createElement("span");
    title.className = "horse-chip";
    title.textContent = label;
    row.appendChild(title);
    list
      .sort((a, b) => unwrap(b.PWin, 0) - unwrap(a.PWin, 0))
      .forEach((horse) => {
        const chip = document.createElement("span");
        chip.className = "horse-chip";
        chip.dataset.lap = unwrap(horse.LapType, "C");
        chip.textContent = `${unwrap(horse.No, "-")} ${unwrap(horse.Name, "-")}`;
        row.appendChild(chip);
      });
    laneTracks.appendChild(row);
  });
}

function unwrap(value, fallback) {
  if (value && typeof value === "object" && "value" in value) {
    return value.value ?? fallback;
  }
  return value ?? fallback;
}

function unwrapList(value) {
  const unwrapped = unwrap(value, []);
  return Array.isArray(unwrapped) ? unwrapped : [];
}
