function setupHeader() {
  const menuButton = document.querySelector("[data-menu-button]");
  const siteNav = document.querySelector("[data-site-nav]");

  if (!menuButton || !siteNav) {
    return;
  }

  const closeMenu = () => {
    menuButton.setAttribute("aria-expanded", "false");
    siteNav.classList.remove("is-open");
    document.body.classList.remove("menu-open");
  };

  const openMenu = () => {
    menuButton.setAttribute("aria-expanded", "true");
    siteNav.classList.add("is-open");
    document.body.classList.add("menu-open");
  };

  menuButton.addEventListener("click", () => {
    const isExpanded = menuButton.getAttribute("aria-expanded") === "true";
    if (isExpanded) {
      closeMenu();
      return;
    }

    openMenu();
  });

  siteNav.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", closeMenu);
  });

  document.addEventListener("click", (event) => {
    if (
      siteNav.classList.contains("is-open") &&
      !siteNav.contains(event.target) &&
      !menuButton.contains(event.target)
    ) {
      closeMenu();
    }
  });

  window.addEventListener("resize", () => {
    if (window.innerWidth > 960) {
      closeMenu();
    }
  });
}

function setupSectionObserver() {
  if (!document.body.classList.contains("page-home")) {
    return;
  }

  const navLinks = Array.from(document.querySelectorAll("[data-section-link]"));
  const sections = navLinks
    .map((link) => document.querySelector(link.getAttribute("href")))
    .filter(Boolean);

  if (!navLinks.length || !sections.length || !("IntersectionObserver" in window)) {
    return;
  }

  const setActive = (id) => {
    navLinks.forEach((link) => {
      const matches = link.getAttribute("href") === `#${id}`;
      link.classList.toggle("is-active", matches);
      if (matches) {
        link.setAttribute("aria-current", "location");
      } else {
        link.removeAttribute("aria-current");
      }
    });
  };

  const visible = new Map();
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          visible.set(entry.target.id, entry.intersectionRatio);
        } else {
          visible.delete(entry.target.id);
        }
      });

      if (window.scrollY < 80) {
        setActive(sections[0].id);
        return;
      }

      let activeId = sections[0].id;
      let bestRatio = -1;

      visible.forEach((ratio, id) => {
        if (ratio > bestRatio) {
          bestRatio = ratio;
          activeId = id;
        }
      });

      setActive(activeId);
    },
    {
      rootMargin: "-20% 0px -55% 0px",
      threshold: [0.05, 0.2, 0.35, 0.5],
    }
  );

  sections.forEach((section) => observer.observe(section));
  setActive(sections[0].id);
}

function formatDate(value) {
  if (!value) {
    return "Unavailable";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en", {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(parsed);
}

function formatNumber(value) {
  return new Intl.NumberFormat("en-US").format(value || 0);
}

function isValidUrl(value) {
  return typeof value === "string" && /^https?:\/\//.test(value);
}

function buildTrendRow(title, info) {
  const row = document.createElement("article");
  row.className = "trend-row";

  const year = document.createElement("div");
  year.className = "trend-year";
  year.textContent = info.year || "N/A";
  row.appendChild(year);

  const main = document.createElement("div");
  main.className = "trend-main";

  const titleEl = document.createElement("h3");
  titleEl.className = "trend-title";
  if (isValidUrl(info.url)) {
    const link = document.createElement("a");
    link.href = info.url;
    link.target = "_blank";
    link.rel = "noopener";
    link.textContent = title;
    titleEl.appendChild(link);
  } else {
    titleEl.textContent = title;
  }
  main.appendChild(titleEl);

  const meta = document.createElement("p");
  meta.className = "trend-meta";
  meta.textContent = `${formatNumber(info.citations)} citations`;
  main.appendChild(meta);

  row.appendChild(main);

  const links = document.createElement("div");
  links.className = "trend-links";

  if (isValidUrl(info.citation_url)) {
    const citationsLink = document.createElement("a");
    citationsLink.href = info.citation_url;
    citationsLink.target = "_blank";
    citationsLink.rel = "noopener";
    citationsLink.textContent = "Citations";
    links.appendChild(citationsLink);
  }

  if (isValidUrl(info.url)) {
    const detailsLink = document.createElement("a");
    detailsLink.href = info.url;
    detailsLink.target = "_blank";
    detailsLink.rel = "noopener";
    detailsLink.textContent = "Scholar record";
    links.appendChild(detailsLink);
  }

  row.appendChild(links);

  return row;
}

function renderTrendCharts(data) {
  if (typeof Chart === "undefined") {
    return;
  }

  const trendCanvas = document.getElementById("citation-trend-chart");
  const impactCanvas = document.getElementById("paper-impact-chart");
  if (!trendCanvas || !impactCanvas) {
    return;
  }

  const styles = getComputedStyle(document.documentElement);
  const textColor = styles.getPropertyValue("--text-soft").trim() || "#3c4a5d";
  const mutedColor = styles.getPropertyValue("--text-muted").trim() || "#6e7a8b";
  const accentColor = styles.getPropertyValue("--accent").trim() || "#1f4f82";
  const ruleColor = styles.getPropertyValue("--rule").trim() || "rgba(59, 74, 93, 0.18)";
  const tintColor = styles.getPropertyValue("--accent-soft").trim() || "#dfeaf6";

  Chart.defaults.color = textColor;
  Chart.defaults.borderColor = ruleColor;
  Chart.defaults.font.family = '"Source Sans 3", "Segoe UI", sans-serif';

  const trendLabels = (data.citation_trend || []).map((item) => item.date);
  const trendValues = (data.citation_trend || []).map((item) => item.citations);

  const sortedPapers = Object.entries(data.papers || {})
    .map(([title, info]) => ({ title, citations: info.citations || 0 }))
    .sort((left, right) => right.citations - left.citations)
    .slice(0, 6);

  new Chart(trendCanvas, {
    type: "line",
    data: {
      labels: trendLabels,
      datasets: [
        {
          data: trendValues,
          borderColor: accentColor,
          backgroundColor: tintColor,
          fill: true,
          borderWidth: 2,
          pointRadius: 2.5,
          pointHoverRadius: 3.5,
          tension: 0.24,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { displayColors: false },
      },
      scales: {
        x: {
          ticks: { color: mutedColor, maxRotation: 0 },
          grid: { display: false },
        },
        y: {
          ticks: { color: mutedColor, precision: 0 },
        },
      },
    },
  });

  new Chart(impactCanvas, {
    type: "bar",
    data: {
      labels: sortedPapers.map((paper) =>
        paper.title.length > 28 ? `${paper.title.slice(0, 28)}...` : paper.title
      ),
      datasets: [
        {
          data: sortedPapers.map((paper) => paper.citations),
          backgroundColor: accentColor,
          borderRadius: 8,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: { displayColors: false },
      },
      scales: {
        x: {
          ticks: { color: mutedColor },
          grid: { display: false },
        },
        y: {
          ticks: { color: mutedColor, precision: 0 },
        },
      },
    },
  });
}

async function initTrendsPage() {
  if (!document.body.classList.contains("page-trends")) {
    return;
  }

  const status = document.getElementById("trends-status");
  const totalCitations = document.getElementById("total-citations");
  const hIndex = document.getElementById("h-index");
  const totalPapers = document.getElementById("total-papers");
  const monthlyGrowth = document.getElementById("monthly-growth");
  const lastUpdated = document.getElementById("trends-last-updated");
  const papersContainer = document.getElementById("papers-container");

  try {
    const response = await fetch("data/scholar_data.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    const papers = Object.entries(data.papers || {}).sort(
      (left, right) => (right[1].citations || 0) - (left[1].citations || 0)
    );
    const trend = data.citation_trend || [];
    const latest = trend[trend.length - 1];
    const previous = trend[trend.length - 2];
    const growth = latest && previous ? latest.citations - previous.citations : 0;

    if (totalCitations) {
      totalCitations.textContent = formatNumber(data.total_citations || 0);
    }
    if (hIndex) {
      hIndex.textContent = formatNumber(data.h_index || 0);
    }
    if (totalPapers) {
      totalPapers.textContent = formatNumber(papers.length);
    }
    if (monthlyGrowth) {
      monthlyGrowth.textContent = `${growth >= 0 ? "+" : ""}${formatNumber(growth)}`;
    }
    if (lastUpdated) {
      lastUpdated.textContent = formatDate(data.last_updated);
    }

    if (papersContainer) {
      papersContainer.innerHTML = "";
      papers.forEach(([title, info]) => {
        papersContainer.appendChild(buildTrendRow(title, info));
      });
    }

    renderTrendCharts(data);

    if (status) {
      status.hidden = true;
    }
  } catch (error) {
    if (status) {
      status.hidden = false;
      status.classList.add("error");
      status.textContent = `Unable to load citation data right now. ${error.message}`;
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  setupHeader();
  setupSectionObserver();
  initTrendsPage();
});
