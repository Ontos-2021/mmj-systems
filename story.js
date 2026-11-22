(() => {
  const story = document.querySelector("[data-scroll-story]");
  if (!story) return;

  const canScrub = Boolean(document.createElement("video").canPlayType('video/mp4; codecs="avc1.640028"'));
  const frame = story.querySelector("[data-story-frame]");
  const stage = story.querySelector(".story-stage");
  const chapters = story.querySelector(".story-chapters");
  const steps = Array.from(chapters.children);
  const counter = story.querySelector("[data-story-count]");
  const toggle = story.querySelector(".story-toggle");
  const header = document.querySelector(".site-header");
  const photos = document.querySelectorAll("[data-depth-photo]");
  const mobile = matchMedia("(max-width: 56rem)");
  const compact = matchMedia("(max-height: 24rem), (max-width: 56rem) and (max-height: 33rem)");
  const reduced = matchMedia("(prefers-reduced-motion: reduce)");
  const connection = navigator.connection;
  let enabled = false;
  let staticView = false;
  let failed = false;
  let engaged = window.scrollY > 0;
  let animation = 0;
  let active = -1;
  let request;
  let loadDeadline;
  let video;
  let objectUrl;

  const visiblePhotos = new Set();
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) visiblePhotos.add(entry.target);
        else visiblePhotos.delete(entry.target);
      }
      schedule();
    }, { rootMargin: "80px 0px" });
    photos.forEach((photo) => observer.observe(photo));
  } else {
    photos.forEach((photo) => visiblePhotos.add(photo));
  }

  const clamp = (value) => Math.max(0, Math.min(1, value));

  function paintDepth(height, headerHeight) {
    const hero = story.getBoundingClientRect();
    const planes = [];
    for (const photo of visiblePhotos) {
      const bounds = photo.getBoundingClientRect();
      if (bounds.bottom <= 0 || bounds.top >= height) continue;
      const progress = clamp((height - bounds.top) / (height + bounds.height));
      planes.push([photo, progress - 0.5]);
    }
    if (hero.bottom > 0 && hero.top < height) {
      const progress = clamp((headerHeight - hero.top) / Math.max(1, hero.height - height));
      story.style.setProperty("--depth-progress", progress);
    }
    for (const [photo, offset] of planes) {
      photo.style.setProperty("--photo-offset", offset);
    }
  }

  function discardMedia() {
    clearTimeout(loadDeadline);
    request?.abort();
    request = undefined;
    if (video) {
      const oldVideo = video;
      video = undefined;
      oldVideo.remove();
      oldVideo.removeAttribute("src");
      oldVideo.load();
    }
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = undefined;
    frame.removeAttribute("data-painted");
  }

  function showFallback() {
    failed = true;
    discardMedia();
    story.setAttribute("data-static", "");
    document.documentElement.removeAttribute("data-depth-motion");
    toggle.hidden = true;
  }

  async function loadMedia() {
    const pending = new AbortController();
    request = pending;
    loadDeadline = setTimeout(() => {
      if (request === pending) showFallback();
    }, 20000);
    try {
      const source = mobile.matches ? frame.dataset.mobile : frame.dataset.desktop;
      // A local Blob keeps the file seekable even on static servers without Range support.
      const response = await fetch(source, { signal: pending.signal, priority: "low" });
      if (!response.ok) throw new Error("Story clip unavailable");
      const blob = await response.blob();
      if (pending.signal.aborted || request !== pending) return;

      objectUrl = URL.createObjectURL(blob);
      const clip = document.createElement("video");
      video = clip;
      clip.setAttribute("aria-hidden", "true");
      clip.defaultMuted = true;
      clip.muted = true;
      clip.playsInline = true;
      clip.preload = "auto";
      clip.disablePictureInPicture = true;
      clip.addEventListener("loadedmetadata", schedule);
      clip.addEventListener("seeked", () => {
        if (video !== clip) return;
        if (clip.readyState >= 2) {
          clearTimeout(loadDeadline);
          frame.setAttribute("data-painted", "");
        }
        schedule();
      });
      clip.addEventListener("loadeddata", () => {
        if (video !== clip) return;
        clearTimeout(loadDeadline);
        if (!clip.seeking && clip.currentTime > 0) {
          frame.setAttribute("data-painted", "");
        }
      });
      clip.addEventListener("error", () => {
        if (video === clip) showFallback();
      }, { once: true });
      frame.append(clip);
      clip.src = objectUrl;
    } catch {
      if (!pending.signal.aborted && request === pending) showFallback();
    }
  }

  function paintStory(progress, current) {
    if (current !== active) {
      steps[active]?.removeAttribute("data-current");
      steps[current].setAttribute("data-current", "");
      active = current;
      counter.textContent = `0${current + 1} / 0${steps.length}`;
    }
    story.style.setProperty("--story-progress", progress);
    // The poster depicts frame zero and is available even while a seek is pending.
    frame.toggleAttribute("data-at-start", progress === 0);
  }

  function seekVideo(progress) {
    // Do not queue a second seek until the decoder finishes the current one.
    if (!video || video.seeking || !Number.isFinite(video.duration)) return;
    const target = progress * Math.max(0, video.duration - 0.042);
    if (Math.abs(video.currentTime - target) > 0.019) {
      try {
        video.currentTime = target;
      } catch {
        showFallback();
      }
    }
  }

  function updateStory(height, headerHeight) {
    if (!canScrub || !engaged) return;
    const region = chapters.getBoundingClientRect();
    if (region.bottom <= 0) return;
    if (region.top > height + 180) {
      // A jump to the logo can leave the film on screen with the chapters far below.
      paintStory(0, 0);
      seekVideo(0);
      return;
    }
    // Track the reading area below the pinned film on mobile, beside it on desktop.
    const line = mobile.matches
      ? Math.min(height - 46, headerHeight + stage.offsetHeight + 34)
      : height * 0.56;
    const last = steps[steps.length - 1].getBoundingClientRect();
    const end = last.bottom - last.height * 0.3;
    const progress = clamp((line - region.top) / Math.max(1, end - region.top));
    let current = 0;
    for (let index = 1; index < steps.length; index++) {
      if (steps[index].getBoundingClientRect().top > line) break;
      current = index;
    }
    paintStory(progress, current);
    if (!request) void loadMedia();
    seekVideo(progress);
  }

  function update() {
    animation = 0;
    if (!enabled || staticView || failed) return;
    const height = window.innerHeight;
    const headerHeight = header.offsetHeight;
    paintDepth(height, headerHeight);
    updateStory(height, headerHeight);
  }

  function schedule() {
    if (enabled && !staticView && !failed && !animation) animation = requestAnimationFrame(update);
  }

  function updateMode() {
    enabled = !(reduced.matches || compact.matches || connection?.saveData);
    story.toggleAttribute("data-motion", enabled && canScrub);
    story.toggleAttribute("data-static", staticView || failed);
    document.documentElement.toggleAttribute("data-depth-motion", enabled && !staticView && !failed);
    toggle.hidden = !enabled || failed;
    if (!enabled || staticView) discardMedia();
    else schedule();
  }

  toggle.addEventListener("click", () => {
    staticView = !staticView;
    toggle.setAttribute("aria-pressed", String(staticView));
    updateMode();
  });
  window.addEventListener("scroll", () => {
    if (window.scrollY > 0) engaged = true;
    schedule();
  }, { passive: true });
  window.addEventListener("resize", schedule);
  window.addEventListener("pagehide", () => {
    cancelAnimationFrame(animation);
    animation = 0;
    discardMedia();
  });
  window.addEventListener("pageshow", schedule);
  mobile.addEventListener("change", () => {
    discardMedia();
    failed = false;
    updateMode();
  });
  reduced.addEventListener("change", updateMode);
  compact.addEventListener("change", updateMode);
  connection?.addEventListener?.("change", updateMode);
  updateMode();
})();
