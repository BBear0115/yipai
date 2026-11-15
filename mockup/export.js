// 导出功能模块 - 单张下载和批量打包

// 生成带时间戳和任务类型的文件名
function generateFilename(job, options = {}) {
  const { index, prefix = '衣拍', extension = 'jpg' } = options;

  // 获取任务类型名称
  let typeName = '作品';
  if (typeof workflowJobName === 'function') {
    typeName = workflowJobName(job)
      .replace(/[·\s]+/g, '_')  // 将 · 和空格替换为单个下划线
      .replace(/_+/g, '_')      // 合并多个连续下划线为一个
      .replace(/^_|_$/g, '');   // 去除首尾下划线
  } else if (job.workflowType) {
    const typeMap = {
      tryon: '虚拟试穿',
      pose_variation: '姿势裂变',
      background_change: '背景替换',
      remake: '拍同款'
    };
    typeName = typeMap[job.workflowType] || (job.model === 'male' ? '男模特' : '女模特');
  } else {
    typeName = job.model === 'male' ? '男模特' : '女模特';
  }

  // 生成时间戳 YYYYMMDD_HHMMSS
  const date = job.created ? new Date(job.created) : new Date();
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  const seconds = String(date.getSeconds()).padStart(2, '0');
  const timestamp = `${year}${month}${day}_${hours}${minutes}${seconds}`;

  // 构建文件名: 衣拍_任务类型_时间戳[_序号].jpg
  const parts = [prefix, typeName, timestamp];
  if (index !== undefined && index !== null) {
    parts.push(String(index));
  }

  return `${parts.join('_')}.${extension}`;
}

// 下载单张图片
function downloadSingleImage(job, imageUrl = null, index = null) {
  const url = imageUrl || job.image;
  if (!url) {
    if (typeof toast === 'function') toast('图片地址无效');
    return;
  }

  const extension = job.localDemo && /\.svg(?:$|[?#])/.test(url) ? 'svg' : 'jpg';
  const filename = generateFilename(job, { index, extension });
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();

  if (typeof toast === 'function') {
    toast('已发起下载，可在下载记录中查看');
  }
}

// 批量下载多张图片（逐个下载，浏览器原生支持）
function downloadMultipleImages(job, images = null) {
  const imageList = images || (Array.isArray(job.images) ? job.images : [job.image].filter(Boolean));

  if (imageList.length === 0) {
    if (typeof toast === 'function') toast('没有可下载的图片');
    return;
  }

  // 逐个下载，每个间隔 300ms 避免浏览器限制
  imageList.forEach((imageUrl, index) => {
    const url = typeof imageUrl === 'string' ? imageUrl : imageUrl?.url;
    if (!url) return;

    setTimeout(() => {
      const extension = job.localDemo && /\.svg(?:$|[?#])/.test(url) ? 'svg' : 'jpg';
      const filename = generateFilename(job, { index: imageList.length > 1 ? index + 1 : undefined, extension });
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
    }, index * 300);
  });

  if (typeof toast === 'function') {
    toast(`已发起 ${imageList.length} 张图片下载`);
  }
}

// 批量下载多个作品的所有图片
function downloadBatchJobs(jobs) {
  if (!Array.isArray(jobs) || jobs.length === 0) {
    if (typeof toast === 'function') toast('没有可下载的作品');
    return;
  }

  const completedJobs = jobs.filter(job => job.status === 'succeeded');
  if (completedJobs.length === 0) {
    if (typeof toast === 'function') toast('暂无已完成的图片');
    return;
  }

  // 下载每个作品的主图，间隔递增避免浏览器限制
  let delay = 0;
  completedJobs.forEach((job, jobIndex) => {
    setTimeout(() => {
      const filename = generateFilename(job, { prefix: `衣拍_批量${jobIndex + 1}` });
      const link = document.createElement('a');
      link.href = job.image;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
    }, delay);
    delay += 400;
  });

  if (typeof toast === 'function') {
    toast(`已发起 ${completedJobs.length} 张图片下载`);
  }
}
