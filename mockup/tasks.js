// Task Queue Visualization for Yipai
const TASK_STATUS_LABELS = {
  queued: '排队中',
  running: '进行中',
  completed: '已完成',
  failed: '失败'
};

const TASK_POLL_INTERVAL = 3000;

let taskData = { tasks: [], grouped: { queued: [], running: [], completed: [], failed: [] } };
let taskFilter = 'all';
let taskPollTimer = null;

async function fetchTasks() {
  try {
    const response = await api('/api/tasks');
    taskData = response;
    return taskData;
  } catch (err) {
    console.error('Failed to fetch tasks:', err);
    throw err;
  }
}

function formatTaskDate(isoString) {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return '刚刚';
  if (diffMins < 60) return `${diffMins}分钟前`;

  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}小时前`;

  return date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

function renderTaskProgress(task) {
  const pct = Math.min(100, Math.max(0, task.progress));
  const countInfo = task.expectedCount > 1
    ? `${task.resultCount}/${task.expectedCount}`
    : '';

  return `
    <div class="task-progress">
      <div class="task-progress-bar">
        <div class="task-progress-fill" style="width: ${pct}%"></div>
      </div>
      <div class="task-progress-text">
        ${pct}% ${countInfo ? `<span class="task-count">${escapeHtml(countInfo)}</span>` : ''}
      </div>
    </div>
  `;
}

function renderTaskCard(task) {
  const statusClass = `task-status-${task.statusGroup}`;
  const statusLabel = TASK_STATUS_LABELS[task.statusGroup] || task.status;
  const showProgress = task.statusGroup === 'running' || (task.statusGroup === 'queued' && task.progress > 0);

  return `
    <div class="task-card ${statusClass}" data-task-id="${escapeHtml(task.id)}">
      <div class="task-header">
        <h3 class="task-title">${escapeHtml(task.title)}</h3>
        <span class="task-badge ${statusClass}">${statusLabel}</span>
      </div>
      ${showProgress ? renderTaskProgress(task) : ''}
      <div class="task-meta">
        <span class="task-time">${formatTaskDate(task.created)}</span>
        ${task.completed ? `<span class="task-completed-time">完成于 ${formatTaskDate(task.completed)}</span>` : ''}
      </div>
    </div>
  `;
}

function getFilteredTasks() {
  if (taskFilter === 'all') {
    return taskData.tasks;
  }
  if (taskFilter === 'active') {
    return [...taskData.grouped.running, ...taskData.grouped.queued];
  }
  return taskData.grouped[taskFilter] || [];
}

function renderTaskList() {
  const filtered = getFilteredTasks();

  if (filtered.length === 0) {
    const emptyMessages = {
      all: '暂无任务',
      active: '没有进行中的任务',
      running: '没有正在运行的任务',
      queued: '没有排队中的任务',
      completed: '没有已完成的任务',
      failed: '没有失败的任务'
    };
    return `<div class="task-empty">${emptyMessages[taskFilter] || '暂无任务'}</div>`;
  }

  return filtered.map(renderTaskCard).join('');
}

function renderTasksPage() {
  const runningCount = taskData.grouped.running.length;
  const queuedCount = taskData.grouped.queued.length;
  const activeCount = runningCount + queuedCount;

  return `
    <div class="tasks-page">
      <header class="page-header">
        <button class="back-button" data-action="back-home">
          <svg viewBox="0 0 24 24">${icons.back}</svg>
        </button>
        <h1>任务中心</h1>
        <div class="header-badge">${activeCount > 0 ? `${activeCount} 个进行中` : ''}</div>
      </header>

      <div class="task-filters">
        <button class="filter-btn ${taskFilter === 'all' ? 'active' : ''}" data-filter="all">
          全部 <span class="filter-count">${taskData.tasks.length}</span>
        </button>
        <button class="filter-btn ${taskFilter === 'active' ? 'active' : ''}" data-filter="active">
          进行中 <span class="filter-count">${activeCount}</span>
        </button>
        <button class="filter-btn ${taskFilter === 'completed' ? 'active' : ''}" data-filter="completed">
          已完成 <span class="filter-count">${taskData.grouped.completed.length}</span>
        </button>
        <button class="filter-btn ${taskFilter === 'failed' ? 'active' : ''}" data-filter="failed">
          失败 <span class="filter-count">${taskData.grouped.failed.length}</span>
        </button>
      </div>

      <div class="task-list">
        ${renderTaskList()}
      </div>

      ${errorSlot}
    </div>
  `;
}

async function refreshTasks() {
  try {
    await fetchTasks();
    if (screen === 'tasks') {
      renderCurrentTasksPage();
    }
  } catch (err) {
    pageError(err.message || '加载任务失败', app, refreshTasks);
  }
}

function renderCurrentTasksPage() {
  app.innerHTML = renderTasksPage();
  attachTasksEventListeners();
}

function attachTasksEventListeners() {
  app.querySelector('[data-action="back-home"]')?.addEventListener('click', () => {
    stopTaskPolling();
    home();
  });

  app.querySelectorAll('[data-filter]').forEach(btn => {
    btn.addEventListener('click', () => {
      taskFilter = btn.dataset.filter;
      renderCurrentTasksPage();
    });
  });

  app.querySelectorAll('.task-card').forEach(card => {
    card.addEventListener('click', () => {
      const taskId = card.dataset.taskId;
      const task = taskData.tasks.find(t => t.id === taskId);
      if (task && task.statusGroup === 'completed') {
        // Navigate to job results if task has associated job ID
        // For now, just go back to home to see the results
        stopTaskPolling();
        home();
      }
    });
  });
}

function startTaskPolling() {
  stopTaskPolling();
  taskPollTimer = setInterval(refreshTasks, TASK_POLL_INTERVAL);
}

function stopTaskPolling() {
  if (taskPollTimer) {
    clearInterval(taskPollTimer);
    taskPollTimer = null;
  }
}

async function openTasksPage() {
  setScreen('tasks', false);
  app.innerHTML = '<div class="loading">加载中...</div>';

  try {
    await fetchTasks();
    renderCurrentTasksPage();
    startTaskPolling();
  } catch (err) {
    app.innerHTML = renderTasksPage();
    pageError(err.message || '加载任务失败', app, openTasksPage);
  }
}

window.openTasksPage = openTasksPage;
window.stopTaskPolling = stopTaskPolling;
