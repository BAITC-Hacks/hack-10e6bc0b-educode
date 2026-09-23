const TOPICS = ['All', 'AI-ML', 'Education', 'FinTech', 'Smart City', 'Healthcare', 'Other'];
const READINESS = ['All', 'RAW', 'SHAPING', 'READY', 'FORGED'];
const LEVEL_LABELS = {
  RAW: 'Черновик',
  SHAPING: 'Рабочая',
  READY: 'Готовая',
  FORGED: 'Приоритетная',
};
const CANVAS_LABELS = {
  title: 'Название',
  context: 'Контекст',
  need: 'Потребность',
  users: 'Пользователи',
  data_materials: 'Данные и материалы',
  constraints: 'Ограничения',
  expected_result: 'Ожидаемый результат',
  success_criteria: 'Критерии успеха',
  contact: 'Контакт',
  interaction_format: 'Формат взаимодействия',
};

const app = document.querySelector('#app');
let renderRevision = 0;
const journey = {
  step: 'IDEA',
  rawIdea: '',
  topic: 'Education',
  challenge: null,
  analysis: null,
  missionIndex: 0,
  answers: {},
  currentQuestion: null,
  refinement: null,
  aiStatus: null,
  beforePosition: null,
};
const catalogState = { topic: 'All', readiness: 'All', search: '' };
let proposalSentFor = null;

function resetJourney() {
  Object.assign(journey, {
    step: 'IDEA',
    rawIdea: '',
    topic: 'Education',
    challenge: null,
    analysis: null,
    missionIndex: 0,
    answers: {},
    currentQuestion: null,
    refinement: null,
    aiStatus: null,
    beforePosition: null,
  });
}

function escapeHtml(value = '') {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
  });
  const text = await response.text();
  let payload = null;
  if (text) {
    try { payload = JSON.parse(text); } catch { payload = text; }
  }
  if (!response.ok) {
    const message = payload?.detail || payload?.message || `Ошибка ${response.status}`;
    throw new Error(Array.isArray(message) ? message.map((item) => item.msg).join('; ') : message);
  }
  return payload;
}

function navigate(path) {
  if (location.pathname === path) {
    render();
    return;
  }
  history.pushState({}, '', path);
  render();
}

function showToast(message, tone = '') {
  const toast = document.createElement('div');
  toast.className = `toast ${tone}`;
  toast.textContent = message;
  document.querySelector('.toast-region').append(toast);
  setTimeout(() => toast.remove(), 3600);
}

function loadingPage(label = 'Загружаем данные') {
  return `<section class="page-shell"><div class="loading-state"><span class="loader"></span><strong>${label}</strong><small>Синхронизируем интерфейс с SANA FORGE</small></div></section>`;
}

function errorPage(error, retryPath = location.pathname) {
  return `<section class="page-shell"><div class="empty-state error-state"><span class="empty-icon">!</span><p class="kicker">Не удалось загрузить экран</p><h1>${escapeHtml(error.message || error)}</h1><p>Проверьте соединение и попробуйте ещё раз.</p><button class="btn" type="button" data-path="${retryPath}">Повторить</button></div></section>`;
}

function pageHeader(kicker, title, subtitle, actions = '') {
  return `<header class="page-head"><div><p class="kicker">${kicker}</p><h1>${title}</h1><p>${subtitle}</p></div>${actions ? `<div class="page-actions">${actions}</div>` : ''}</header>`;
}

function chips(items, tone = '') {
  return (items || []).map((item) => `<span class="chip ${tone}">${escapeHtml(item)}</span>`).join('');
}

function scoreOrb(score, level, size = '') {
  return `<div class="score-orb ${size}" style="--score:${score}"><div><strong>${score}</strong><span>/100</span></div></div><span class="level-pill ${level.toLowerCase()}">${level} · ${LEVEL_LABELS[level]}</span>`;
}

function sanaBot(size = '') {
  return `<span class="sana-bot ${size}" aria-hidden="true"><i class="bot-antenna"></i><i class="bot-face"><b></b><b></b></i><i class="bot-body"></i></span>`;
}

function workspaceFrame(content, active = 'home', role = 'business') {
  const items = role === 'business'
    ? [
      ['home', '/', '⌂', 'Главная'],
      ['create', '/business/new', '+', 'Создать задачу'],
      ['dashboard', '/business/dashboard', '▣', 'Мои задачи'],
      ['catalog', '/catalog', '◇', 'Каталог задач'],
      ['teams', '/teams', '◎', 'Команды'],
    ]
    : [
      ['home', '/student', '⌂', 'Главная'],
      ['catalog', '/catalog', '◇', 'Каталог задач'],
      ['teams', '/teams', '◎', 'Команды'],
      ['profile', '/teams/1', '○', 'Мой профиль'],
    ];
  return `<div class="workspace-layout ${role}"><aside class="workspace-sidebar"><nav>${items.map(([key, path, icon, label]) => `<button class="${active === key ? 'active' : ''}" type="button" data-path="${path}"><span>${icon}</span>${label}</button>`).join('')}</nav><div class="sidebar-story"><strong>${role === 'business' ? 'Инновации начинаются с реальных задач' : 'Большие идеи начинаются с тебя'}</strong><div class="story-landscape"><i></i><i></i><i></i></div><button type="button" data-path="${role === 'business' ? '/business/new' : '/catalog'}">→</button></div><p class="sidebar-sign">SANA <b>FORGE</b><br><span>Реальные задачи. Реальные решения.</span></p></aside><div class="workspace-main">${content}</div></div>`;
}

function journeyHeading(kicker, title, subtitle) {
  return `<header class="journey-heading"><p class="kicker">${kicker}</p><h1>${title}</h1><p>${subtitle}</p></header>`;
}

function topicArtwork(topic, index = 0) {
  const icons = { 'AI-ML': 'AI', Education: 'EDU', FinTech: '₸', 'Smart City': 'CITY', Healthcare: '+', Other: 'IDEA' };
  return `<div class="topic-art topic-${String(topic).toLowerCase().replace(/[^a-z]+/g, '-') || 'other'} tone-${index % 4}"><span>${icons[topic] || 'AI'}</span><i></i><i></i><i></i></div>`;
}

function updateHeader(path) {
  const business = path.startsWith('/business');
  const team = path === '/student' || path.startsWith('/catalog') || path.startsWith('/challenges') || path.startsWith('/teams');
  document.querySelectorAll('.role-switch [data-role]').forEach((button) => {
    button.classList.toggle('active', (button.dataset.role === 'business' && business) || (button.dataset.role === 'team' && team));
  });
  document.querySelectorAll('.desktop-nav [data-path]').forEach((button) => {
    const target = button.dataset.path;
    button.classList.toggle('active', path === target || (target === '/catalog' && path.startsWith('/challenges')) || (target === '/teams' && /^\/teams\//.test(path)));
  });
}

async function renderHome() {
  const [stats, challenges] = await Promise.all([api('/api/stats'), api('/api/challenges')]);
  const featured = challenges.slice(0, 3);
  return `<section class="landing sana-landing">
    <div class="sana-hero">
      <div class="hero-copy">
        <p class="hero-overline">PRACTICAL CHALLENGES. BRIGHTER TOMORROW.</p>
        <h1>От бизнес-проблемы<br>к <em>реальному<br>решению</em></h1>
        <p class="hero-lead">AI-платформа практических вызовов<br>для бизнеса и студенческих команд.</p>
        <div class="hero-actions"><button class="btn hero-cta" type="button" data-scroll="roles">Вместе создаём больше возможностей <span>→</span></button></div>
        <div class="hero-owner"><span class="owner-emblem">✦</span><p>Владелец кейса:<br><b>МНВО — AI Sana</b></p></div>
      </div>
      <div class="hero-world" aria-label="People, ideas, opportunities and impact">
        <div class="city-sun"></div><div class="astana-line"><i></i><i></i><i></i><i></i><i></i><b></b></div>
        <div class="glass-flow flow-one"></div><div class="glass-flow flow-two"></div>
        <div class="hero-orbit"></div>
        <div class="glass-card idea-card"><small>IDEA</small><span>◉</span><b>REAL BUSINESS<br>PROBLEMS</b></div>
        <div class="glass-card sana-card"><span class="sana-mini-mark">⌃</span><b>SANA AI</b></div>
        <div class="glass-card impact-card"><small>IMPACT</small><span>▥</span><b>FORGED<br>CHALLENGES</b></div>
        <p class="world-motto">PEOPLE　×　IDEAS　×　OPPORTUNITIES　×　IMPACT</p>
      </div>
    </div>
    <section class="role-section" id="roles">
      <header><p class="kicker">Добро пожаловать в SANA FORGE</p><h2>Кто вы?</h2><p>Выберите, чтобы продолжить</p></header>
      <div class="role-cards">
        <article class="role-card business-card"><div><span class="role-label">БИЗНЕС</span><h3>Я представитель<br>бизнеса</h3><p>Опишите реальную задачу, получите поддержку SANA AI и найдите студенческие команды для её решения.</p><button class="btn dark" type="button" data-path="/business/new">Создать задачу <span>→</span></button></div><div class="role-scene office-scene"><span class="scene-note">Ваша идея может стать реальным решением</span><i class="desk"></i><i class="chair"></i><i class="screen"></i></div></article>
        <article class="role-card student-card"><div><span class="role-label">СТУДЕНТЫ / КОМАНДА</span><h3>Я студент<br>или команда</h3><p>Ищите интересные задачи, предлагайте свои решения, развивайте навыки и работайте с реальными кейсами.</p><button class="btn dark" type="button" data-path="/student">Найти задачи <span>→</span></button></div><div class="role-scene student-scene"><span class="scene-note">Твои навыки меняют Казахстан</span><i class="laptop"></i><i class="books"></i><i class="plant"></i></div></article>
      </div>
      <div class="benefit-row"><div><span>▥</span><b>Реальные задачи<br>от бизнеса</b></div><div><span>✦</span><b>Поддержка AI<br>на каждом этапе</b></div><div><span>◈</span><b>Развитие навыков<br>и опыта</b></div><div><span>♧</span><b>Вклад в будущее<br>Казахстана</b></div></div>
    </section>
    <section class="home-market"><header><p class="kicker">Challenge marketplace</p><h2>Актуальные задачи</h2><button class="text-link" type="button" data-path="/catalog">Смотреть все →</button></header><div class="home-market-grid">${featured.map((item, index) => `<article class="home-market-card" data-path="/challenges/${item.id}" tabindex="0" role="link">${topicArtwork(item.topic, index)}<div class="chip-row"><span class="chip">${escapeHtml(item.topic)}</span><span class="level-pill ${item.level.toLowerCase()}">${item.level}</span></div><h3>${escapeHtml(item.canvas.title)}</h3><p>${escapeHtml(item.canvas.need || item.canvas.context || 'Описание уточняется')}</p><footer><b>${item.score}</b><span>Forge Score</span><strong>${item.proposal_count} предложений</strong></footer></article>`).join('')}</div><div class="real-counter-row"><div><strong>${stats.published_challenges}</strong><span>опубликованных задач</span></div><div><strong>${stats.teams}</strong><span>команд</span></div><div><strong>${stats.proposals}</strong><span>предложений</span></div></div></section>
  </section>`;
}

async function renderStudentHome() {
  const [stats, challenges, teams] = await Promise.all([api('/api/stats'), api('/api/challenges'), api('/api/teams')]);
  const featured = challenges.slice(0, 3);
  return workspaceFrame(`<section class="page-shell student-home-page"><div class="student-welcome"><div><p class="kicker">SANA FORGE · STUDENT</p><h1>Большие идеи<br>начинаются с тебя</h1><p>Решай реальные задачи. Учись. Развивайся.<br>Создавай изменения вместе с SANA Forge.</p><button class="btn warm" type="button" data-path="/catalog">Перейти к задачам →</button></div><div class="student-desk"><span>Students shape a<br>brighter tomorrow</span><i></i><b></b></div></div>
    <div class="student-stats"><div><strong>${stats.teams}</strong><span>активных команд</span></div><div><strong>${stats.published_challenges}</strong><span>реальных задач</span></div><div><strong>${stats.proposals}</strong><span>предложений</span></div><div><strong>${teams.reduce((sum, team) => sum + team.points, 0)}</strong><span>подтверждённых баллов</span></div></div>
    <div class="student-section-head"><div><p class="kicker">Marketplace</p><h2>Популярные задачи</h2></div><button class="text-link" type="button" data-path="/catalog">Смотреть все →</button></div><div class="student-featured">${featured.map((item, index) => `<article data-path="/challenges/${item.id}" role="link" tabindex="0">${topicArtwork(item.topic, index)}<span class="chip">${escapeHtml(item.topic)}</span><h3>${escapeHtml(item.canvas.title)}</h3><p>${escapeHtml(item.canvas.need || item.canvas.context || '')}</p><footer><b>${item.score} score</b><span>${item.proposal_count} заявок</span></footer></article>`).join('')}</div>
  </section>`, 'home', 'team');
}

function journeyStepper() {
  const steps = ['IDEA', 'REFINE', 'CONFIRM', 'SCORE', 'PUBLISH'];
  const labels = ['Описание', 'Уточнение с AI', 'Редактирование', 'Расчёт рейтинга', 'Публикация'];
  const current = steps.indexOf(journey.step);
  return `<div class="journey-stepper">${steps.map((step, index) => `<div class="journey-step ${index < current ? 'done' : ''} ${index === current ? 'active' : ''}"><span>${index < current ? '✓' : index + 1}</span><b>${step}</b><small>${labels[index]}</small>${index < steps.length - 1 ? '<i></i>' : ''}</div>`).join('')}</div>`;
}

function renderIdea(stats) {
  return `${journeyHeading('Создание задачи', 'Расскажите <em>о вашей задаче</em>', 'Опишите реальную проблему вашего бизнеса своими словами. SANA AI поможет уточнить детали и превратить её в качественный Challenge для студенческих команд.')}
  <div class="creation-grid design-idea-grid">
    <article class="surface creation-main idea-form-card">
      <div class="field"><label for="raw-idea">Опишите вашу задачу</label><textarea id="raw-idea" maxlength="3000" placeholder="Например: «Мы хотим автоматизировать обработку заявок клиентов, но не знаем, с чего начать. У нас много входящих обращений…»">${escapeHtml(journey.rawIdea)}</textarea><div class="field-meta"><span>Расскажите о проблеме без подробного ТЗ</span><span id="idea-count">${journey.rawIdea.length} / 3000</span></div></div>
      <div class="idea-fields"><div class="field"><label for="idea-topic">Отрасль / тема</label><select id="idea-topic">${TOPICS.filter((topic) => topic !== 'All').map((topic) => `<option ${journey.topic === topic ? 'selected' : ''}>${topic}</option>`).join('')}</select></div><div class="field"><label for="idea-tags">Теги <span>(необязательно)</span></label><input id="idea-tags" placeholder="Например: AI, аналитика, образование"></div></div>
      <div class="idea-tip"><span>💡</span><p>Не составляйте подробное ТЗ. Достаточно описать проблему — остальное мы уточним вместе с SANA AI.</p></div>
      <div class="creation-actions"><button class="btn quiet" type="button" data-action="save-idea-draft">▣ Сохранить черновик</button><button class="btn wide-cta" type="button" data-action="analyze-idea">Анализировать с SANA AI <span>→</span></button></div>
    </article>
    <aside class="idea-side-stack"><article class="surface ai-welcome-card"><div class="ai-welcome-head">${sanaBot('large')}<div><h3>SANA AI</h3><span><i></i> Ваш AI-ассистент</span></div></div><div class="ai-speech">Опишите задачу, как если бы вы рассказывали коллеге. Я помогу выделить ключевые аспекты, задать уточняющие вопросы и предложить структуру решения.</div></article><article class="surface readiness-card"><h3>Ваш текущий прогресс <span>ⓘ</span></h3><div class="readiness-body"><div>${scoreOrb(0, 'RAW')}</div><p><b>После анализа<br>и уточнения информации</b><br>ваша готовность будет расти.</p></div></article><article class="surface ai-quote"><span>“</span><p>«Хорошо сформулированная задача — уже половина решения.»</p><small>AI Sana</small></article></aside>
  </div>`;
}

function missionSuggestions(field) {
  const options = {
    context: ['Обработка занимает слишком много времени', 'Высокая нагрузка на сотрудников', 'Нет единой системы'],
    need: ['Сократить ручную работу', 'Уменьшить число ошибок', 'Ускорить обработку'],
    users: ['Клиенты компании', 'Сотрудники', 'Операторы поддержки'],
    data_materials: ['Обезличенная база данных', 'Логи системы', 'Примеры заявок'],
    expected_result: ['Рабочий прототип', 'AI-помощник', 'Аналитическая панель'],
    success_criteria: ['Время обработки −50%', 'Точность не ниже 90%', 'Проверка на тестовой выборке'],
    constraints: ['Только учебные данные', 'API-доступ', 'Срок 6 недель'],
    contact: ['Еженедельный созвон', 'Контакт в Telegram', 'Обратная связь раз в неделю'],
    interaction_format: ['Онлайн-встречи', 'Чат и демо', 'Еженедельные ревью'],
  };
  return options[field] || ['Указать подтверждённые данные', 'Обсудить с командой', 'Не указано'];
}

function renderRefine() {
  const analysis = journey.analysis;
  const mission = journey.currentQuestion || analysis.questions[0];
  const turns = journey.challenge?.ai_turns || [];
  const answered = journey.refinement?.answered_questions ?? turns.length;
  const readiness = journey.refinement?.potential_score ?? journey.challenge?.ai_preview_score ?? 0;
  const level = journey.refinement?.potential_level || (readiness < 40 ? 'RAW' : readiness < 70 ? 'SHAPING' : readiness < 90 ? 'READY' : 'FORGED');
  const suggestions = missionSuggestions(mission.target_field);
  const lastTurn = turns.at(-1);
  const liveAI = journey.aiStatus?.live ?? !journey.refinement?.fallback_used;
  const criteria = Object.values(journey.refinement?.breakdown || journey.challenge?.ai_preview_breakdown || {});
  return `${journeyHeading('Уточнение задачи с AI', 'Уточняем вашу задачу <em>с AI</em>', 'Чем подробнее вы опишете задачу, тем полнее будет Challenge Canvas и тем больше шансов привлечь подходящие студенческие команды.')}
  <div class="refine-layout conversation-layout">
    <article class="surface mission-stage chat-stage">
      <div class="chat-agent"><div>${sanaBot('large')}<span><b>SANA AI</b><small><i></i> ${liveAI ? `Реальный AI${journey.aiStatus?.model ? ` · ${escapeHtml(journey.aiStatus.model)}` : ''}` : 'Безопасный fallback'}</small></span></div><strong>Вопрос ${answered + 1}<small>${escapeHtml(mission.mission)}</small></strong></div>
      <div class="mission-progress dynamic"><i class="active" style="width:${Math.max(4, readiness)}%"></i></div>
      <div class="chat-thread">${lastTurn ? `<div class="user-message"><div>${escapeHtml(lastTurn.answer)}</div><span>B</span></div><div class="ai-feedback">✓ ${escapeHtml(lastTurn.feedback)}</div>` : ''}<div class="bot-message">${sanaBot()}<div><b>${escapeHtml(mission.question)}</b><p>${escapeHtml(mission.hint)}</p><small>AI спрашивает только о недостающих данных</small></div></div><p class="example-label">Примеры ответов:</p><div class="suggestion-row">${suggestions.map((item) => `<button type="button" data-suggestion="${escapeHtml(item)}">${escapeHtml(item)}</button>`).join('')}</div></div>
      <div class="chat-composer"><textarea id="mission-answer" rows="1" placeholder="Напишите конкретный ответ…"></textarea><button type="button" data-action="mission-next" aria-label="Отправить ответ">➤</button></div>
      <div class="mission-footer"><span>Минимум 3 уточнения</span><span>AI продолжит до готовности 80–100</span></div>
    </article>
    <aside class="refine-score-rail"><article class="surface forge-preview"><h3>Прогноз готовности <span>ⓘ</span></h3><div class="preview-score"><div class="score-orb" style="--score:${readiness}"><div><strong>${readiness}</strong><span>/100</span></div></div><div><b>${Math.max(0, 80 - readiness)}</b><span>до целевого уровня 80</span></div></div><span class="level-pill ${level.toLowerCase()}">${level}</span><p>Прогноз рассчитывает backend. Официальный Forge Score появится только после подтверждения Canvas бизнесом.</p></article><article class="surface criteria-preview"><div class="criteria-head"><h3>Прогресс по критериям</h3><span>${answered} ответов</span></div>${criteria.map((item, index) => `<div class="criteria-row"><span>${item.complete ? '✓' : index + 1}</span><div><b>${escapeHtml(item.label)}</b><i><em style="width:${item.max_points ? item.points / item.max_points * 100 : 0}%"></em></i><small>${item.points}/${item.max_points}</small></div></div>`).join('')}</article><article class="surface ai-quote compact"><span>“</span><p>Чем точнее задача, тем больше возможностей для сильной команды.</p><small>AI Sana</small></article></aside>
  </div>`;
}

function canvasValue(field) {
  return journey.challenge?.canvas?.[field] || journey.answers[field] || journey.analysis?.canvas?.[field] || '';
}

function renderConfirm() {
  const textareas = new Set(['context', 'need', 'data_materials', 'expected_result', 'success_criteria']);
  return `${journeyHeading('Challenge Canvas', 'Проверьте и <em>подтвердите</em> задачу', 'SANA AI структурировал ответы. Отредактируйте формулировки и подтвердите только достоверные данные.')}<article class="surface canvas-shell">
    <div class="canvas-intro"><div><p class="kicker">Challenge Canvas</p><h2>Проверьте каждое утверждение</h2><p>AI структурировал ваши ответы. Исправьте формулировки и оставьте «Не указано» там, где данных пока нет.</p></div><div class="canvas-seal"><span>HUMAN</span><b>CONFIRM</b></div></div>
    <form id="canvas-form" class="canvas-form">
      ${Object.entries(CANVAS_LABELS).map(([field, label]) => `<div class="field ${field === 'title' ? 'wide' : ''}"><label for="canvas-${field}">${label}</label>${textareas.has(field) ? `<textarea id="canvas-${field}" name="${field}" placeholder="Не указано">${escapeHtml(canvasValue(field))}</textarea>` : `<input id="canvas-${field}" name="${field}" value="${escapeHtml(canvasValue(field))}" placeholder="Не указано">`}</div>`).join('')}
      <div class="field wide"><label for="canvas-topic">Тема</label><select id="canvas-topic" name="topic">${TOPICS.filter((item) => item !== 'All').map((item) => `<option ${journey.topic === item ? 'selected' : ''}>${item}</option>`).join('')}</select></div>
      <label class="confirmation-box wide"><input id="business-confirmation" type="checkbox"><span><b>Я подтверждаю факты в Challenge Canvas</b><small>Forge Score будет начислен только за заполненные и подтверждённые поля.</small></span></label>
    </form>
    <div class="canvas-actions"><button class="btn quiet" type="button" data-action="back-to-missions">← К Missions</button><div><button class="btn secondary" type="button" data-action="save-canvas">Сохранить без подтверждения</button><button class="btn" type="button" data-action="confirm-canvas">Подтвердить и рассчитать Score <span>→</span></button></div></div>
  </article>`;
}

function renderScore() {
  const challenge = journey.challenge;
  const breakdown = Object.values(challenge.breakdown);
  const history = [0, ...challenge.score_history].filter((value, index, array) => index === 0 || value !== array[index - 1]);
  return `${journeyHeading('Почти готово', 'Опубликуйте <em>вашу задачу</em>', 'Проверьте Forge Score и недостающую информацию. После публикации Challenge станет доступен всем студенческим командам.')}<div class="score-layout">
    <article class="surface score-hero"><p class="kicker">Backend Forge Score</p>${scoreOrb(challenge.score, challenge.level, 'large')}<p class="score-caption">Результат рассчитан кодом по подтверждённым полям. AI не участвует в формуле.</p><div class="score-history"><span>Рост Score</span><div>${history.map((score, index) => `${index ? '<i>→</i>' : ''}<b>${score}</b>`).join('')}</div></div></article>
    <article class="surface breakdown-card"><div class="card-heading"><div><p class="kicker">Breakdown</p><h2>Из чего сложился результат</h2></div><span>${challenge.score}/100</span></div><div class="breakdown-list">${breakdown.map((item) => `<div class="breakdown-row"><div><b>${escapeHtml(item.label)}</b>${item.missing_fields.length ? `<small>Не указано: ${escapeHtml(item.missing_fields.join(', '))}</small>` : '<small class="complete-copy">Подтверждено</small>'}</div><div class="breakdown-track"><i style="width:${item.points / item.max_points * 100}%"></i></div><strong>${item.points}<span>/${item.max_points}</span></strong></div>`).join('')}</div>${challenge.missing_information.length ? `<div class="soft-note warning"><b>Что улучшить</b><p>${escapeHtml(challenge.missing_information.join(' · '))}</p></div>` : '<div class="soft-note success"><b>Canvas заполнен полностью</b><p>Challenge готов к приоритетной публикации.</p></div>'}</article>
    <article class="surface position-card"><p class="kicker">Projected catalog position</p><div class="position-jump"><span>#${journey.beforePosition || challenge.projected_position}</span><i>→</i><strong>#${challenge.projected_position}</strong></div><p>Позиция вычисляется по опубликованным Challenges, отсортированным по Score.</p><div class="position-actions"><button class="btn quiet" type="button" data-action="edit-canvas">Редактировать Canvas</button><button class="btn" type="button" data-action="publish-challenge">Опубликовать Challenge <span>↗</span></button></div></article>
  </div>`;
}

function renderPublished() {
  const challenge = journey.challenge;
  return `<article class="published-scene"><div class="publish-rays"></div><span class="success-mark">✓</span><p class="kicker light">Challenge is live</p><h2>${escapeHtml(challenge.canvas.title)}</h2><p>Теперь Challenge доступен всем студенческим командам без ограничений по уровню готовности.</p><div class="published-metrics"><div><strong>${challenge.score}</strong><span>Forge Score</span></div><div><strong>#${challenge.position}</strong><span>позиция в каталоге</span></div><div><strong>${challenge.level}</strong><span>${LEVEL_LABELS[challenge.level]}</span></div></div><div class="hero-actions"><button class="btn light" type="button" data-path="/challenges/${challenge.id}">Открыть Challenge</button><button class="btn glass" type="button" data-path="/catalog">Перейти в каталог</button><button class="btn glass" type="button" data-action="new-journey">Создать ещё</button></div></article>`;
}

async function renderBusinessNew() {
  const stats = journey.step === 'IDEA' ? await api('/api/stats') : null;
  let stage = '';
  if (journey.step === 'IDEA') stage = renderIdea(stats);
  if (journey.step === 'REFINE') stage = renderRefine();
  if (journey.step === 'CONFIRM') stage = renderConfirm();
  if (journey.step === 'SCORE') stage = renderScore();
  if (journey.step === 'PUBLISH') stage = renderPublished();
  return workspaceFrame(`<section class="page-shell creation-page"><div class="creation-topline"><button class="back-link" type="button" data-path="/">← На главную</button>${journey.challenge ? '<button class="btn quiet small" type="button" data-action="new-journey">+ Новый Challenge</button>' : ''}</div>${journeyStepper()}${stage}</section>`, 'create', 'business');
}

function challengeCard(challenge) {
  const canvas = challenge.canvas;
  return `<article class="market-card" data-path="/challenges/${challenge.id}" tabindex="0" role="link">
    ${topicArtwork(challenge.topic, challenge.id)}<div class="market-top"><span class="chip">${escapeHtml(challenge.topic)}</span><span class="level-pill ${challenge.level.toLowerCase()}">${challenge.level}</span></div>
    <h2>${escapeHtml(canvas.title || 'Challenge без названия')}</h2><p>${escapeHtml(canvas.need || canvas.context || 'Описание уточняется')}</p>
    <div class="market-tags">${challenge.missing_information.slice(0, 2).map((item) => `<span>○ ${escapeHtml(item)}</span>`).join('') || '<span class="ready-copy">✓ Canvas подтверждён</span>'}</div>
    <footer><div class="market-score"><strong>${challenge.score}</strong><span>Forge<br>Score</span></div><div><b>${challenge.proposal_count}</b><span>предложений</span></div><span class="round-arrow">↗</span></footer>
  </article>`;
}

async function renderCatalog() {
  const params = new URLSearchParams();
  if (catalogState.topic !== 'All') params.set('topic', catalogState.topic);
  if (catalogState.readiness !== 'All') params.set('readiness', catalogState.readiness);
  const challenges = await api(`/api/challenges?${params}`);
  return workspaceFrame(`<section class="page-shell catalog-page">${pageHeader('Challenge marketplace', 'Каталог реальных задач', 'Выберите Challenge, предложите решение и получите подтверждённые баллы за результат.', '<button class="btn secondary" type="button" data-path="/teams">Профили команд</button>')}
    <div class="catalog-toolbar surface"><div class="search-wrap"><span>⌕</span><input id="catalog-search" value="${escapeHtml(catalogState.search)}" placeholder="Поиск по задачам"></div><div class="filter-group"><small>Тема</small><div class="chip-row">${TOPICS.map((topic) => `<button class="filter-chip ${catalogState.topic === topic ? 'active' : ''}" type="button" data-topic="${topic}">${topic}</button>`).join('')}</div></div><div class="filter-group"><small>Готовность</small><div class="chip-row">${READINESS.map((level) => `<button class="filter-chip ${catalogState.readiness === level ? 'active' : ''}" type="button" data-readiness="${level}">${level}</button>`).join('')}</div></div></div>
    <div class="catalog-meta"><span><b>${challenges.length}</b> Challenges</span><span>Сортировка: <b>Forge Score ↓</b></span></div>
    <div class="market-grid" id="market-grid">${challenges.map(challengeCard).join('') || '<div class="empty-state"><span class="empty-icon">◇</span><h2>Подходящих Challenges пока нет</h2><p>Измените фильтры — низкий Score не скрывает опубликованные задачи.</p></div>'}</div>
  </section>`, 'catalog', 'team');
}

async function renderChallengeDetail(challengeId) {
  const [challenge, teams] = await Promise.all([api(`/api/challenges/${challengeId}`), api('/api/teams')]);
  const canvas = challenge.canvas;
  const sent = proposalSentFor === challenge.id;
  return workspaceFrame(`<section class="page-shell challenge-page"><button class="back-link" type="button" data-path="/catalog">← Назад к каталогу</button><div class="challenge-detail">
    <article class="challenge-story"><div class="challenge-banner">${topicArtwork(challenge.topic, challenge.id)}<div><span>${escapeHtml(challenge.topic)}</span><h2>${escapeHtml(canvas.title)}</h2></div></div><div class="story-head"><div class="chip-row"><span class="chip">${escapeHtml(challenge.topic)}</span><span class="level-pill ${challenge.level.toLowerCase()}">${challenge.level}</span></div><div class="detail-score"><strong>${challenge.score}</strong><span>Forge Score<br>#${challenge.position} в каталоге</span></div></div><h1>${escapeHtml(canvas.title)}</h1><p class="story-lead">${escapeHtml(canvas.need || canvas.context || 'Не указано')}</p><div class="detail-facts"><span>◎ ${escapeHtml(canvas.users || 'Пользователи уточняются')}</span><span>◷ ${escapeHtml(canvas.constraints || 'Срок не указан')}</span><span>◇ ${challenge.proposal_count} предложений</span></div><div class="canvas-readout">${Object.entries(CANVAS_LABELS).filter(([field]) => field !== 'title').map(([field, label]) => `<div><span>${label}</span><p>${escapeHtml(canvas[field] || 'Не указано')}</p></div>`).join('')}</div></article>
    <aside class="proposal-panel surface">${sent ? `<div class="proposal-success"><span class="success-mark small">✓</span><p class="kicker">Proposal sent</p><h2>Предложение отправлено</h2><p>Бизнес увидит его в кабинете и самостоятельно примет решение.</p><button class="btn" type="button" data-path="/teams/${teams[0].id}">Профиль команды</button></div>` : `<p class="kicker">Team proposal</p><h2>Предложить решение</h2><form id="proposal-form"><div class="field"><label for="proposal-team">Команда</label><select id="proposal-team" name="team_id">${teams.map((team) => `<option value="${team.id}">${escapeHtml(team.name)} · ${team.points} баллов</option>`).join('')}</select></div><div class="field"><label for="proposal-idea">Идея решения</label><textarea id="proposal-idea" name="idea" placeholder="Как именно вы решите задачу?" required></textarea></div><div class="field"><label for="proposal-plan">План реализации</label><textarea id="proposal-plan" name="plan" placeholder="Шаги, проверка гипотезы и результат" required></textarea></div><div class="field-grid"><div class="field"><label for="proposal-deadline">Срок</label><input id="proposal-deadline" name="deadline" value="6 недель" required></div><div class="field"><label for="proposal-url">Prototype / GitHub</label><input id="proposal-url" name="prototype_url" type="url" placeholder="https://github.com/..."></div></div><button class="btn full" type="button" data-action="submit-proposal" data-challenge="${challenge.id}">Отправить Proposal <span>→</span></button><small>Количество предложений не ограничено. Решение принимает только бизнес.</small></form>`}</aside>
  </div></section>`, 'catalog', 'team');
}

async function renderTeams() {
  const teams = await api('/api/teams');
  return workspaceFrame(`<section class="page-shell teams-page">${pageHeader('Student talent', 'Команды AI Sana', 'Навыки, интересы и реальные баллы за подтверждённые этапы.')}
    <div class="team-market">${teams.map((team, index) => `<article class="team-market-card" data-path="/teams/${team.id}" tabindex="0" role="link"><div class="team-card-head"><span class="team-avatar tone-${index % 5}">${escapeHtml(team.initials)}</span><div class="team-points"><strong>${team.points}</strong><small>points</small></div></div><h2>${escapeHtml(team.name)}</h2><p>${escapeHtml(team.interests.join(' · '))}</p><div class="skill-cloud">${chips(team.technologies)}</div><footer><span>${team.skills.length} ключевых навыка</span><b>Профиль ↗</b></footer></article>`).join('')}</div>
  </section>`, 'teams', 'team');
}

function proposalCard(proposal) {
  const pending = proposal.status === 'PENDING';
  return `<article class="dashboard-proposal"><div class="team-avatar compact">${escapeHtml(proposal.initials)}</div><div class="proposal-copy"><div><h3>${escapeHtml(proposal.team_name)}</h3><span class="status-pill ${proposal.status.toLowerCase()}">${proposal.status}</span></div><p>${escapeHtml(proposal.challenge_title)}</p><small>${escapeHtml(proposal.idea)}</small></div><div class="decision-actions">${pending ? `<button class="btn success small" type="button" data-decision="SELECTED" data-proposal="${proposal.id}">Select</button><button class="btn danger small" type="button" data-decision="DECLINED" data-proposal="${proposal.id}">Decline</button>` : `<button class="btn quiet small" type="button" data-path="/teams/${proposal.team_id}">Открыть команду</button>`}</div></article>`;
}

function progressBlock(proposal, team) {
  const stages = team.progress.filter((stage) => stage.challenge_id === proposal.challenge_id);
  if (!stages.length) return '';
  const completed = stages.filter((stage) => stage.status === 'COMPLETED').length;
  const nextPending = stages.find((stage) => stage.status === 'PENDING');
  return `<article class="surface progress-block"><div class="progress-block-head"><div><p class="kicker">Active delivery</p><h3>${escapeHtml(proposal.challenge_title)}</h3><span>${escapeHtml(team.name)} · ${completed}/3 этапов</span></div><button class="text-link" type="button" data-path="/teams/${team.id}">${team.points} points ↗</button></div><div class="delivery-steps">${stages.map((stage) => `<div class="delivery-step ${stage.status === 'COMPLETED' ? 'done' : ''}"><span>${stage.status === 'COMPLETED' ? '✓' : stage.stage_number}</span><div><b>${escapeHtml(stage.name)}</b><small>${stage.points} points</small></div></div>`).join('')}</div>${nextPending ? `<div class="progress-confirm"><p>Только бизнес подтверждает выполнение. После подтверждения баллы начислятся backend-кодом.</p><button class="btn small" type="button" data-action="confirm-stage" data-challenge="${proposal.challenge_id}" data-team="${team.id}" data-stage="${nextPending.stage_number}">Подтвердить ${escapeHtml(nextPending.name)} (+${nextPending.points})</button></div>` : '<div class="soft-note success"><b>Все этапы завершены</b><p>Результат и история баллов сохранены.</p></div>'}</article>`;
}

async function renderDashboard() {
  const dashboard = await api('/api/business/dashboard');
  const selected = dashboard.proposals.filter((proposal) => proposal.status === 'SELECTED');
  const uniqueTeamIds = [...new Set(selected.map((proposal) => proposal.team_id))];
  const teamProfiles = await Promise.all(uniqueTeamIds.map((id) => api(`/api/teams/${id}`)));
  const teamMap = Object.fromEntries(teamProfiles.map((team) => [team.id, team]));
  const published = dashboard.challenges.filter((challenge) => challenge.published);
  return workspaceFrame(`<section class="page-shell dashboard-page">${pageHeader('Business workspace', 'Мои задачи и предложения', 'Вы можете выбрать одну, несколько или ни одной команды. Решение принимает бизнес.', '<button class="btn" type="button" data-path="/business/new">+ Создать задачу</button>')}
    <div class="dashboard-metrics"><div><span>Опубликовано</span><strong>${published.length}</strong></div><div><span>Новые proposals</span><strong>${dashboard.proposals.filter((item) => item.status === 'PENDING').length}</strong></div><div><span>Выбрано команд</span><strong>${selected.length}</strong></div><div><span>Средний Score</span><strong>${published.length ? Math.round(published.reduce((sum, item) => sum + item.score, 0) / published.length) : 0}</strong></div></div>
    <div class="dashboard-grid"><section><div class="section-heading"><div><p class="kicker">Incoming proposals</p><h2>Предложения команд</h2></div><span>${dashboard.proposals.length}</span></div><div class="proposal-list">${dashboard.proposals.map(proposalCard).join('') || '<div class="empty-state compact"><h3>Предложений пока нет</h3></div>'}</div></section><aside class="surface challenge-summary"><p class="kicker">Your portfolio</p><h2>Опубликованные Challenges</h2>${published.slice(0, 6).map((challenge) => `<button type="button" data-path="/challenges/${challenge.id}"><span class="level-dot ${challenge.level.toLowerCase()}"></span><div><b>${escapeHtml(challenge.canvas.title)}</b><small>${challenge.proposal_count} предложений · #${challenge.position}</small></div><strong>${challenge.score}</strong></button>`).join('')}</aside></div>
    ${selected.length ? `<section class="progress-section"><div class="section-heading"><div><p class="kicker">Progress & points</p><h2>Выполнение выбранных решений</h2></div></div><div class="progress-grid">${selected.map((proposal) => progressBlock(proposal, teamMap[proposal.team_id])).join('')}</div></section>` : ''}
  </section>`, 'dashboard', 'business');
}

async function renderTeamProfile(teamId) {
  const team = await api(`/api/teams/${teamId}`);
  const grouped = team.progress.reduce((result, stage) => {
    (result[stage.challenge_id] ||= { title: stage.challenge_title, stages: [] }).stages.push(stage);
    return result;
  }, {});
  return workspaceFrame(`<section class="page-shell team-profile-page"><button class="back-link" type="button" data-path="/teams">← Все команды</button><div class="profile-hero"><span class="team-avatar huge">${escapeHtml(team.initials)}</span><div><p class="kicker light">Student team</p><h1>${escapeHtml(team.name)}</h1><p>${escapeHtml(team.interests.join(' · '))}</p><div class="chip-row">${chips(team.technologies, 'dark')}</div></div><div class="profile-points"><strong>${team.points}</strong><span>impact<br>points</span></div></div>
    <div class="profile-grid"><article class="surface profile-card"><p class="kicker">Capabilities</p><h2>Навыки команды</h2><div class="capability-list">${team.skills.map((skill, index) => `<div><span>0${index + 1}</span><b>${escapeHtml(skill)}</b></div>`).join('')}</div><div class="soft-note"><b>${team.proposal_count} proposals</b><p>Количество предложений не ограничено.</p></div></article><article class="surface profile-card wide"><p class="kicker">Team progress</p><h2>Активные Challenges</h2>${Object.values(grouped).length ? Object.values(grouped).map((group) => `<div class="team-progress-item"><div><b>${escapeHtml(group.title)}</b><span>${group.stages.filter((item) => item.status === 'COMPLETED').length} / 3 этапов</span></div><div class="mini-stage-row">${group.stages.map((stage) => `<span class="${stage.status === 'COMPLETED' ? 'done' : ''}" title="${escapeHtml(stage.name)}">${stage.status === 'COMPLETED' ? '✓' : stage.stage_number}</span>`).join('')}</div></div>`).join('') : '<div class="empty-state compact"><h3>Пока нет активных этапов</h3><p>Отправьте Proposal на подходящий Challenge.</p><button class="btn small" data-path="/catalog">Открыть каталог</button></div>'}</article></div>
    <article class="surface points-history"><div class="section-heading"><div><p class="kicker">Verified impact</p><h2>История начислений</h2></div><strong>+${team.point_history.reduce((sum, item) => sum + item.points, 0)}</strong></div>${team.point_history.length ? `<div class="history-list">${team.point_history.map((item) => `<div><span>+${item.points}</span><p><b>${escapeHtml(item.reason)}</b><small>${new Date(item.created_at).toLocaleDateString('ru-RU')}</small></p></div>`).join('')}</div>` : '<p class="muted">Баллы появятся после подтверждения этапа бизнесом.</p>'}</article>
  </section>`, 'profile', 'team');
}

function notFoundPage() {
  return `<section class="page-shell"><div class="empty-state"><span class="empty-icon">404</span><p class="kicker">Маршрут не найден</p><h1>Такой страницы нет</h1><p>Вернитесь на главную или откройте каталог Challenges.</p><div class="page-actions"><button class="btn" data-path="/">На главную</button><button class="btn secondary" data-path="/catalog">Каталог</button></div></div></section>`;
}

async function routeContent(path) {
  if (path === '/') return renderHome();
  if (path === '/student') return renderStudentHome();
  if (path === '/business/new') return renderBusinessNew();
  if (path === '/catalog') return renderCatalog();
  if (path === '/teams') return renderTeams();
  if (path === '/business/dashboard') return renderDashboard();
  const challengeMatch = path.match(/^\/challenges\/(\d+)$/);
  if (challengeMatch) return renderChallengeDetail(Number(challengeMatch[1]));
  const teamMatch = path.match(/^\/teams\/(\d+)$/);
  if (teamMatch) return renderTeamProfile(Number(teamMatch[1]));
  return notFoundPage();
}

async function render() {
  const revision = ++renderRevision;
  const path = location.pathname.replace(/\/$/, '') || '/';
  updateHeader(path);
  app.innerHTML = loadingPage();
  try {
    const content = await routeContent(path);
    if (revision !== renderRevision) return;
    app.innerHTML = content;
    if (path === '/catalog' && catalogState.search) {
      const query = catalogState.search.toLowerCase().trim();
      document.querySelectorAll('.market-card').forEach((card) => {
        card.hidden = !card.textContent.toLowerCase().includes(query);
      });
    }
    const heading = app.querySelector('h1, h2');
    const pageTitle = (heading?.innerText || heading?.textContent || 'SANA FORGE').replace(/\s+/g, ' ').trim();
    document.title = `${path === '/' ? 'SANA FORGE' : pageTitle} · AI Sana`;
    app.focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: 'instant' });
  } catch (error) {
    if (revision !== renderRevision) return;
    app.innerHTML = errorPage(error);
  }
}

function collectCanvas() {
  const form = document.querySelector('#canvas-form');
  if (!form) throw new Error('Canvas form is unavailable');
  const formData = new FormData(form);
  const canvas = {};
  Object.keys(CANVAS_LABELS).forEach((field) => { canvas[field] = formData.get(field)?.trim() || null; });
  return { canvas, topic: formData.get('topic') };
}

async function handleAction(button) {
  const action = button.dataset.action;
  if (action === 'save-idea-draft') {
    journey.rawIdea = document.querySelector('#raw-idea').value.trim();
    journey.topic = document.querySelector('#idea-topic').value;
    showToast('Текст сохранён в текущей сессии', 'success');
    return;
  }
  if (action === 'analyze-idea') {
    const rawIdea = document.querySelector('#raw-idea').value.trim();
    const topic = document.querySelector('#idea-topic').value;
    if (rawIdea.length < 20) throw new Error('Опишите проблему минимум в 20 символах');
    button.disabled = true;
    button.innerHTML = 'SANA AI анализирует <span class="inline-loader"></span>';
    const result = await api('/api/challenges/draft', { method: 'POST', body: JSON.stringify({ raw_idea: rawIdea, topic }) });
    journey.rawIdea = rawIdea;
    journey.topic = topic;
    journey.challenge = result.challenge;
    journey.analysis = result.analysis;
    journey.missionIndex = 0;
    journey.answers = {};
    journey.currentQuestion = result.refinement.next_question;
    journey.refinement = result.refinement;
    journey.aiStatus = result.ai_status;
    journey.step = 'REFINE';
    await render();
    return;
  }
  if (action === 'mission-next') {
    const answer = document.querySelector('#mission-answer').value.trim();
    if (!answer) throw new Error('Добавьте подтверждённый ответ, чтобы продолжить');
    const mission = journey.currentQuestion || journey.analysis.questions[0];
    button.disabled = true;
    button.textContent = '…';
    const result = await api(`/api/challenges/${journey.challenge.id}/refine`, {
      method: 'POST',
      body: JSON.stringify({ question: mission, answer }),
    });
    journey.challenge = result.challenge;
    journey.refinement = result.refinement;
    journey.currentQuestion = result.refinement.next_question;
    journey.aiStatus = result.ai_status;
    if (result.refinement.ready_for_canvas) {
      journey.step = 'CONFIRM';
      showToast(`Задача понятна: прогноз готовности ${result.refinement.potential_score}/100`, 'success');
    }
    await render();
    return;
  }
  if (action === 'mission-back') {
    journey.missionIndex = Math.max(0, journey.missionIndex - 1);
    await render(); return;
  }
  if (action === 'back-to-missions') {
    journey.step = 'REFINE'; journey.missionIndex = journey.analysis.questions.length - 1;
    await render(); return;
  }
  if (action === 'save-canvas' || action === 'confirm-canvas') {
    if (action === 'confirm-canvas' && !document.querySelector('#business-confirmation').checked) {
      throw new Error('Подтвердите факты в Challenge Canvas');
    }
    const payload = collectCanvas();
    const updated = await api(`/api/challenges/${journey.challenge.id}/canvas`, { method: 'PUT', body: JSON.stringify(payload) });
    journey.challenge = updated;
    journey.topic = payload.topic;
    journey.beforePosition = updated.projected_position;
    if (action === 'save-canvas') { showToast('Canvas сохранён. Для Score нужно подтверждение бизнеса.', 'success'); return; }
    journey.challenge = await api(`/api/challenges/${journey.challenge.id}/confirm`, { method: 'POST', body: JSON.stringify({ confirmed: true }) });
    journey.step = 'SCORE';
    await render(); return;
  }
  if (action === 'edit-canvas') { journey.step = 'CONFIRM'; await render(); return; }
  if (action === 'publish-challenge') {
    button.disabled = true;
    journey.challenge = await api(`/api/challenges/${journey.challenge.id}/publish`, { method: 'POST' });
    journey.step = 'PUBLISH';
    await render(); return;
  }
  if (action === 'new-journey') {
    resetJourney();
    await render(); return;
  }
  if (action === 'submit-proposal') {
    const form = document.querySelector('#proposal-form');
    if (!form.reportValidity()) return;
    const values = Object.fromEntries(new FormData(form).entries());
    const payload = { team_id: Number(values.team_id), idea: values.idea.trim(), plan: values.plan.trim(), deadline: values.deadline.trim(), prototype_url: values.prototype_url.trim() || null };
    if (payload.idea.length < 10 || payload.plan.length < 10) throw new Error('Идея и план должны содержать минимум 10 символов');
    await api(`/api/challenges/${button.dataset.challenge}/proposals`, { method: 'POST', body: JSON.stringify(payload) });
    proposalSentFor = Number(button.dataset.challenge);
    showToast('Proposal отправлен бизнесу', 'success');
    await render(); return;
  }
  if (action === 'confirm-stage') {
    await api(`/api/challenges/${button.dataset.challenge}/teams/${button.dataset.team}/stages/${button.dataset.stage}/confirm`, { method: 'POST' });
    showToast('Этап подтверждён. Баллы начислены backend-кодом.', 'success');
    await render();
  }
}

document.addEventListener('click', async (event) => {
  const scrollTarget = event.target.closest('[data-scroll]');
  if (scrollTarget) {
    document.getElementById(scrollTarget.dataset.scroll)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    return;
  }
  const pathTarget = event.target.closest('[data-path]');
  if (pathTarget) {
    if (pathTarget.dataset.path === '/business/new') resetJourney();
    navigate(pathTarget.dataset.path);
    document.querySelector('.mobile-menu').hidden = true;
    return;
  }
  const role = event.target.closest('[data-role]');
  if (role) {
    if (role.dataset.role === 'business') resetJourney();
    navigate(role.dataset.role === 'business' ? '/business/new' : '/student');
    return;
  }
  const menuButton = event.target.closest('.menu-button');
  if (menuButton) {
    const menu = document.querySelector('.mobile-menu');
    menu.hidden = !menu.hidden;
    menuButton.setAttribute('aria-expanded', String(!menu.hidden));
    return;
  }
  const topic = event.target.closest('[data-topic]');
  if (topic) { catalogState.topic = topic.dataset.topic; await render(); return; }
  const readiness = event.target.closest('[data-readiness]');
  if (readiness) { catalogState.readiness = readiness.dataset.readiness; await render(); return; }
  const suggestion = event.target.closest('[data-suggestion]');
  if (suggestion) {
    const input = document.querySelector('#mission-answer');
    if (input) { input.value = suggestion.dataset.suggestion; input.focus(); }
    return;
  }
  const decision = event.target.closest('[data-decision]');
  if (decision) {
    try {
      await api(`/api/proposals/${decision.dataset.proposal}`, { method: 'PATCH', body: JSON.stringify({ status: decision.dataset.decision }) });
      showToast(decision.dataset.decision === 'SELECTED' ? 'Команда выбрана. Этапы созданы.' : 'Proposal отклонён.', 'success');
      await render();
    } catch (error) { showToast(error.message, 'error'); }
    return;
  }
  const action = event.target.closest('[data-action]');
  if (action) {
    try { await handleAction(action); }
    catch (error) { action.disabled = false; showToast(error.message, 'error'); }
  }
});

document.addEventListener('keydown', (event) => {
  const card = event.target.closest('[role="link"][data-path]');
  if (card && (event.key === 'Enter' || event.key === ' ')) { event.preventDefault(); navigate(card.dataset.path); }
});

document.addEventListener('input', (event) => {
  if (event.target.id === 'raw-idea') {
    journey.rawIdea = event.target.value;
    const count = document.querySelector('#idea-count');
    if (count) count.textContent = `${event.target.value.length} / 3000`;
  }
  if (event.target.id === 'catalog-search') {
    catalogState.search = event.target.value;
    const query = event.target.value.toLowerCase().trim();
    document.querySelectorAll('.market-card').forEach((card) => { card.hidden = !card.textContent.toLowerCase().includes(query); });
  }
});

window.addEventListener('popstate', render);
render();
