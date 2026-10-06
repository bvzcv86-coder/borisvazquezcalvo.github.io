'use strict';

(() => {
  const form = document.getElementById('publication-filters');
  if (!form) return;
  const search = document.getElementById('publication-search');
  const topic = document.getElementById('publication-topic');
  const year = document.getElementById('publication-year');
  const count = document.getElementById('publication-meta');
  const empty = document.getElementById('publication-empty');
  const normalise = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const records = [...document.querySelectorAll('#publication-list .publication')].map(element => ({
    element,
    text: normalise(element.textContent),
    year: element.dataset.year,
    topics: JSON.parse(element.dataset.topics)
  }));
  const filter = () => {
    const terms = normalise(search.value.trim()).split(/\s+/).filter(Boolean);
    let shown = 0;
    records.forEach(record => {
      const matches = terms.every(term => record.text.includes(term)) &&
        (!topic.value || record.topics.includes(topic.value)) && (!year.value || record.year === year.value);
      record.element.hidden = !matches;
      if (matches) shown += 1;
    });
    count.textContent = `${shown} of ${records.length} publications`;
    empty.hidden = shown !== 0;
  };
  form.hidden = false;
  form.addEventListener('submit', event => event.preventDefault());
  form.addEventListener('input', filter);
  form.addEventListener('change', filter);
  form.addEventListener('reset', () => requestAnimationFrame(filter));
})();
