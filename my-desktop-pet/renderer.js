// DOM元素
const petContainer = document.querySelector(".pet-container");
const pixelCat = document.querySelector(".pixel-cat");
const controlPanel = document.querySelector(".control-panel");
const statusText = document.getElementById("status-text");
const messageInput = document.getElementById("message-input");
const sendButton = document.getElementById("send-button");
const voiceButton = document.getElementById("voice-button");
const feedButton = document.getElementById("feed-button");
const voiceStatus = document.getElementById("voice-status");
const closeButton = document.querySelector(".close-button");
const notification = document.querySelector(".notification");
const catPawLeft = document.querySelector(".cat-paw-left");
const catPawRight = document.querySelector(".cat-paw-right");
const catTail = document.querySelector(".cat-tail");
const catMouth = document.querySelector(".cat-mouth");
const contextMenu = document.querySelector(".context-menu");
const crazyModeToggle = document.getElementById("crazy-mode-toggle");
const blurEffect = document.querySelector(".blur-effect");
const particlesContainer = document.querySelector(".particles-container");

// 状态变量
let isMovingFreely = false;
let moveInterval = null;
let isDragging = false;
let startX, startY, initialX, initialY;
let lastInteractionTime = Date.now();
let isHungry = false;
let isHappy = false;
let isThinking = false;
let isCrazyMode = false;
let crazyInterval = null;
let rightClickCount = 0;
let rightClickTimer = null;
let currentCostume = "pepper";
let websocket = null;

// WebSocket连接
function initWebSocket() {
  const wsUrl = "ws://localhost:8765";
  websocket = new WebSocket(wsUrl);

  websocket.onopen = () => {
    console.log("WebSocket连接已建立");
    updateStatus("已连接到服务器", "#32CD32");
  };

  websocket.onmessage = (event) => {
    const message = JSON.parse(event.data);
    console.log("收到消息:", message);

    if (message.type === "connection_ack") {
      updateStatus("已连接到服务器", "#32CD32");
    } else if (message.type === "status") {
      updateStatus(message.message, "#32CD32");
    } else if (message.type === "plan_status") {
      updateStatus(message.message, "#32CD32");
    } else if (message.type === "tool_execution") {
      updateStatus(`工具执行: ${message.tool} - ${message.status}`, "#4169E1");
    } else if (message.type === "step_completed") {
      updateStatus(`步骤完成: ${message.index}`, "#4169E1");
    } else if (message.type === "error") {
      updateStatus(`错误: ${message.message}`, "#FF6347");
    }
  };

  websocket.onerror = (error) => {
    console.error("WebSocket错误:", error);
    updateStatus("连接到服务器失败", "#FF6347");
  };

  websocket.onclose = () => {
    console.log("WebSocket连接已关闭");
    updateStatus("连接已断开", "#FF6347");
    // 尝试重新连接
    setTimeout(initWebSocket, 5000);
  };
}

// 初始化WebSocket连接
initWebSocket();

// 更新状态
function updateStatus(message, color) {
  statusText.textContent = message;
  statusText.style.borderColor = color || "#32CD32";
}

// 显示通知
function showNotification(message) {
  notification.textContent = message;
  notification.classList.add("show");

  setTimeout(() => {
    notification.classList.remove("show");
  }, 3000);
}

// 猫咪弹跳动画
function bounceCat() {
  pixelCat.classList.remove("bounce");
  void pixelCat.offsetWidth; // 触发重绘
  pixelCat.classList.add("bounce");

  setTimeout(() => {
    pixelCat.classList.remove("bounce");
  }, 500);
}

// 猫爪挥动动画
function wavePaws() {
  // 左爪挥动
  catPawLeft.classList.remove("wave-left");
  void catPawLeft.offsetWidth; // 触发重绘
  catPawLeft.classList.add("wave-left");

  // 右爪挥动
  catPawRight.classList.remove("wave-right");
  void catPawRight.offsetWidth; // 触发重绘
  catPawRight.classList.add("wave-right");

  setTimeout(() => {
    catPawLeft.classList.remove("wave-left");
    catPawRight.classList.remove("wave-right");
  }, 500);
}

// 猫尾巴摇动
function wagTail(shouldWag) {
  if (shouldWag) {
    catTail.classList.add("wag-tail");
  } else {
    catTail.classList.remove("wag-tail");
  }
}

// 设置思考状态
function setThinkingState(thinking) {
  isThinking = thinking;
  if (thinking) {
    pixelCat.classList.add("thinking");
  } else {
    pixelCat.classList.remove("thinking");
  }
}

// 设置饥饿状态
function setHungryState(hungry) {
  isHungry = hungry;
  if (hungry) {
    petContainer.classList.add("hungry");
    catMouth.classList.add("hungry");
    updateStatus("我饿了...", "#FF6347");
    showNotification("喵~ 我好饿...");
  } else {
    petContainer.classList.remove("hungry");
    catMouth.classList.remove("hungry");
    updateStatus("桌面宠物已启动", "#32CD32");
  }
}

// 设置愉悦状态
function setHappyState(happy) {
  isHappy = happy;
  if (happy) {
    petContainer.classList.add("happy");
    wagTail(true);
    updateStatus("我好开心！", "#4169E1");
    showNotification("喵~ 谢谢喂食！");

    setTimeout(() => {
      setHappyState(false);
    }, 10000);
  } else {
    petContainer.classList.remove("happy");
    wagTail(false);
    updateStatus("桌面宠物已启动", "#32CD32");
  }
}

// 检查互动时间
function checkInteractionTime() {
  const currentTime = Date.now();
  const timeSinceLastInteraction = currentTime - lastInteractionTime;

  // 5分钟没有互动就变成饥饿状态
  if (timeSinceLastInteraction > 5 * 60 * 1000 && !isHungry && !isHappy) {
    setHungryState(true);
  }
}

// 更新互动时间
function updateInteractionTime() {
  lastInteractionTime = Date.now();
  if (isHungry) {
    // 互动后如果是饥饿状态，不会立即恢复，需要喂食
    showNotification("喵~ 我还是好饿...");
  }
}

// 喂食
function feedPet() {
  if (isHungry) {
    // 创建食物元素
    const food = document.createElement("div");
    food.className = "food";

    // 随机选择食物类型
    const foodTypes = ["fish", "milk"];
    const foodType = foodTypes[Math.floor(Math.random() * foodTypes.length)];
    food.classList.add(foodType);

    // 放置在宠物附近
    const petRect = petContainer.getBoundingClientRect();
    food.style.left = `${petRect.left + petRect.width / 2 - 10}px`;
    food.style.top = `${petRect.top + petRect.height - 20}px`;

    document.body.appendChild(food);

    // 食物移动到嘴边
    setTimeout(() => {
      const mouthRect = catMouth.getBoundingClientRect();
      food.style.left = `${mouthRect.left + mouthRect.width / 2 - 10}px`;
      food.style.top = `${mouthRect.top + mouthRect.height / 2 - 10}px`;
      food.style.transform = "scale(0.5)";

      // 吃掉食物
      setTimeout(() => {
        food.classList.add("eaten");
        setHungryState(false);
        setHappyState(true);

        // 移除食物元素
        setTimeout(() => {
          document.body.removeChild(food);
        }, 500);
      }, 1000);
    }, 500);
  } else {
    showNotification("喵~ 我现在不饿~");
  }
}

// 切换疯狂模式
function toggleCrazyMode() {
  isCrazyMode = !isCrazyMode;

  if (isCrazyMode) {
    petContainer.classList.add("crazy-mode");
    showNotification("Yo! 疯狂模式已开启！");

    // 开始随机疯狂行为
    crazyInterval = setInterval(() => {
      const randomAction = Math.random();

      if (randomAction < 0.3) {
        // 随机系统通知
        const messages = ["快喝水！", "坐久了要起来活动一下！", "记得眨眼睛！", "该休息了！", "Yo! 看什么看！"];
        const randomMessage = messages[Math.floor(Math.random() * messages.length)];
        showSystemNotification("桌面宠物提醒", randomMessage);
      } else if (randomAction < 0.6) {
        // 随机说唱语音
        const rapLines = [
          "Yo! 主人你瞅啥！",
          "猫猫说唱冠军在此！",
          "喵喵个喵，我是说唱之王！",
          "瞧好了，这就是我的地盘！",
          "喵了个咪的，看我的节奏！",
        ];
        const randomRap = rapLines[Math.floor(Math.random() * rapLines.length)];
        showNotification(randomRap);

        // 如果浏览器支持语音合成
        if ("speechSynthesis" in window) {
          const utterance = new SpeechSynthesisUtterance(randomRap);
          utterance.rate = 1.2; // 稍快的语速
          utterance.pitch = 1.5; // 更高的音调
          speechSynthesis.speak(utterance);
        }
      }
    }, 15000); // 每15秒随机一次
  } else {
    petContainer.classList.remove("crazy-mode");
    showNotification("疯狂模式已关闭");
    clearInterval(crazyInterval);
  }
}

// 切换装扮
function changeCostume(costume) {
  // 移除当前装扮的active类
  document.querySelector(`.${currentCostume}-cat`).classList.remove("active");

  // 添加新装扮的active类
  document.querySelector(`.${costume}-cat`).classList.add("active");

  // 更新当前装扮
  currentCostume = costume;

  // 根据装扮更新状态文本颜色
  let color = "#32CD32"; // 默认青椒绿色
  if (costume === "tofu") {
    color = "#8B4513"; // 豆干棕色
  } else if (costume === "blueberry") {
    color = "#4169E1"; // 蓝莓蓝色
  }

  statusText.style.borderColor = color;

  // 显示通知
  const messages = {
    pepper: "喵~ 我变成青椒猫啦！",
    tofu: "喵~ 我变成豆干猫啦！",
    blueberry: "喵~ 我变成蓝莓猫啦！",
  };

  showNotification(messages[costume]);
  bounceCat();
}

// 创建粒子效果
function createParticle(x, y, type) {
  const particle = document.createElement("div");
  particle.className = "particle";
  particle.classList.add(type);

  // 随机大小
  const size = Math.random() * 15 + 5;
  particle.style.width = `${size}px`;
  particle.style.height = `${size}px`;

  // 设置位置
  particle.style.left = `${x}px`;
  particle.style.top = `${y}px`;

  // 随机旋转
  particle.style.transform = `rotate(${Math.random() * 360}deg)`;

  // 添加到容器
  particlesContainer.appendChild(particle);

  // 随机动画
  const duration = Math.random() * 3 + 2;
  const xMove = (Math.random() - 0.5) * 100;
  const yMove = Math.random() * 100 + 50;

  particle.animate(
    [
      { transform: `translate(0, 0) rotate(0deg)`, opacity: 0.8 },
      { transform: `translate(${xMove}px, ${yMove}px) rotate(${Math.random() * 360}deg)`, opacity: 0 },
    ],
    {
      duration: duration * 1000,
      easing: "ease-out",
    }
  );

  // 动画结束后移除粒子
  setTimeout(() => {
    particlesContainer.removeChild(particle);
  }, duration * 1000);
}

// 创建拖动粒子效果
function createDragParticles(x, y) {
  // 随机创建1-3个粒子
  const count = Math.floor(Math.random() * 3) + 1;
  const types = ["leaf", "star"];

  for (let i = 0; i < count; i++) {
    // 随机选择粒子类型
    const type = types[Math.floor(Math.random() * types.length)];
    // 在鼠标位置附近随机生成粒子
    const offsetX = (Math.random() - 0.5) * 20;
    const offsetY = (Math.random() - 0.5) * 20;
    createParticle(x + offsetX, y + offsetY, type);
  }
}

// 自由移动功能
function toggleFreeMovement() {
  isMovingFreely = !isMovingFreely;

  if (isMovingFreely) {
    // 开始自由移动
    wagTail(true);
    startRandomMovement();
    showNotification("喵~ 我要自由啦！");
  } else {
    // 停止自由移动
    wagTail(false);
    stopRandomMovement();
    showNotification("喵~ 我累了...");
  }
}

// 开始随机移动
function startRandomMovement() {
  if (moveInterval) {
    clearInterval(moveInterval);
  }

  moveInterval = setInterval(() => {
    // 获取当前位置
    const currentX = Number.parseInt(petContainer.style.left) || 20;
    const currentY = Number.parseInt(petContainer.style.top) || 20;

    // 随机移动方向和距离
    const moveX = Math.random() * 40 - 20; // -20 到 20 之间
    const moveY = Math.random() * 40 - 20; // -20 到 20 之间

    // 计算新位置
    const newX = currentX + moveX;
    const newY = currentY + moveY;

    // 确保不超出屏幕边界
    const maxX = window.innerWidth - petContainer.offsetWidth;
    const maxY = window.innerHeight - petContainer.offsetHeight;

    petContainer.style.left = `${Math.max(0, Math.min(newX, maxX))}px`;
    petContainer.style.top = `${Math.max(0, Math.min(newY, maxY))}px`;

    // 随机挥动猫爪
    if (Math.random() > 0.8) {
      wavePaws();
    }
  }, 1000);
}

// 停止随机移动
function stopRandomMovement() {
  if (moveInterval) {
    clearInterval(moveInterval);
    moveInterval = null;
  }
}

// 显示右键菜单
function showContextMenu(x, y) {
  contextMenu.style.left = `${x}px`;
  contextMenu.style.top = `${y}px`;
  contextMenu.classList.add("show");

  // 点击其他地方关闭菜单
  document.addEventListener("click", hideContextMenu);
}

// 隐藏右键菜单
function hideContextMenu() {
  contextMenu.classList.remove("show");
  document.removeEventListener("click", hideContextMenu);
}

// 点击猫咪显示控制面板并挥动猫爪 (左键点击)
pixelCat.addEventListener("click", (e) => {
  if (e.button === 0) {
    // 左键点击
    e.stopPropagation(); // 阻止事件冒泡

    // 如果正在自由移动，则停止
    if (isMovingFreely) {
      toggleFreeMovement();
    }

    // 弹跳动画
    bounceCat();

    // 挥动猫爪
    wavePaws();

    // 显示控制面板
    controlPanel.classList.add("show");

    // 计算控制面板位置
    const petRect = petContainer.getBoundingClientRect();
    controlPanel.style.left = `${petRect.left + petRect.width / 2}px`;
    controlPanel.style.top = `${petRect.bottom + 10}px`;

    // 随机喵喵声
    const meows = ["喵~", "喵喵~", "喵？", "喵！", "喵..."];
    const randomMeow = meows[Math.floor(Math.random() * meows.length)];
    showNotification(randomMeow);

    // 更新互动时间
    updateInteractionTime();
  }
});

// 右键点击处理
pixelCat.addEventListener("contextmenu", (e) => {
  e.preventDefault(); // 阻止默认右键菜单
  e.stopPropagation();

  // 检测双击
  rightClickCount++;

  if (rightClickCount === 1) {
    rightClickTimer = setTimeout(() => {
      rightClickCount = 0;
      // 单击右键 - 切换自由移动
      toggleFreeMovement();
      bounceCat();
    }, 300);
  } else if (rightClickCount === 2) {
    clearTimeout(rightClickTimer);
    rightClickCount = 0;

    // 双击右键 - 显示自定义菜单
    showContextMenu(e.clientX, e.clientY);
  }

  // 更新互动时间
  updateInteractionTime();
});

// 菜单项点击事件
document.querySelectorAll(".menu-item[data-costume]").forEach((item) => {
  item.addEventListener("click", () => {
    const costume = item.getAttribute("data-costume");
    changeCostume(costume);
    hideContextMenu();
  });
});

// 疯狂模式切换
crazyModeToggle.addEventListener("click", () => {
  toggleCrazyMode();
  hideContextMenu();
});

// 关闭控制面板
closeButton.addEventListener("click", () => {
  controlPanel.classList.remove("show");
  wavePaws(); // 关闭时也挥动猫爪
});

// 点击其他地方关闭控制面板
document.addEventListener("click", (e) => {
  if (!controlPanel.contains(e.target) && !pixelCat.contains(e.target)) {
    controlPanel.classList.remove("show");
  }
});

// 输入框焦点事件 - 思考状态
messageInput.addEventListener("focus", () => {
  setThinkingState(true);
});

messageInput.addEventListener("blur", () => {
  setThinkingState(false);
});

// 发送消息
sendButton.addEventListener("click", () => {
  const message = messageInput.value.trim();
  if (message) {
    messageInput.value = "";
    bounceCat();
    wavePaws(); // 发送消息时挥动猫爪
    showNotification("喵~ 已收到！");
    setThinkingState(false);

    // 更新互动时间
    updateInteractionTime();

    // 发送消息到WebSocket服务器
    if (websocket && websocket.readyState === WebSocket.OPEN) {
      websocket.send(JSON.stringify({
        type: "prompt",
        data: message
      }));
    }
  }
});

// 按Enter键发送消息
messageInput.addEventListener("keypress", (e) => {
  if (e.key === "Enter") {
    sendButton.click();
  }
});

// 喂食按钮
feedButton.addEventListener("click", () => {
  feedPet();

  // 更新互动时间
  updateInteractionTime();
});

// 语音按钮功能
voiceButton.addEventListener("click", () => {
  if ("webkitSpeechRecognition" in window) {
    const SpeechRecognition = window.webkitSpeechRecognition || window.SpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.lang = "zh-CN";

    voiceButton.classList.add("listening");
    voiceStatus.textContent = "正在听...";
    wavePaws(); // 开始语音识别时挥动猫爪

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      messageInput.value = transcript;
      voiceStatus.textContent = "";
      voiceButton.classList.remove("listening");
      wavePaws(); // 语音识别结束时挥动猫爪
    };

    recognition.onerror = () => {
      voiceStatus.textContent = "语音识别失败";
      voiceButton.classList.remove("listening");
    };

    recognition.onend = () => {
      voiceButton.classList.remove("listening");
      if (voiceStatus.textContent === "正在听...") {
        voiceStatus.textContent = "";
      }
    };

    recognition.start();
  } else {
    voiceStatus.textContent = "浏览器不支持语音识别";
  }

  // 更新互动时间
  updateInteractionTime();
});

// 拖动功能 - 允许在整个屏幕上移动 (左键拖动)
petContainer.addEventListener("mousedown", (e) => {
  if (e.button === 0) {
    // 左键点击
    // 如果正在自由移动，则停止
    if (isMovingFreely) {
      toggleFreeMovement();
    }

    isDragging = true;
    startX = e.clientX;
    startY = e.clientY;
    initialX = petContainer.offsetLeft;
    initialY = petContainer.offsetTop;

    // 激活模糊效果
    blurEffect.classList.add("active");

    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);

    // 更新互动时间
    updateInteractionTime();
  }
});

function onMouseMove(e) {
  if (!isDragging) return;

  const newX = initialX + (e.clientX - startX);
  const newY = initialY + (e.clientY - startY);

  // 无边界移动 - 当宠物移出屏幕一侧时，从另一侧出现
  const screenWidth = window.innerWidth;
  const screenHeight = window.innerHeight;

  // 计算实际位置，考虑屏幕环绕
  const wrappedX = ((newX % screenWidth) + screenWidth) % screenWidth;
  const wrappedY = ((newY % screenHeight) + screenHeight) % screenHeight;

  petContainer.style.left = `${wrappedX}px`;
  petContainer.style.top = `${wrappedY}px`;

  // 如果控制面板是显示状态，更新它的位置
  if (controlPanel.classList.contains("show")) {
    const petRect = petContainer.getBoundingClientRect();
    controlPanel.style.left = `${petRect.left + petRect.width / 2}px`;
    controlPanel.style.top = `${petRect.bottom + 10}px`;
  }

  // 创建拖动粒子效果
  if (Math.random() > 0.7) {
    createDragParticles(e.clientX, e.clientY);
  }
}

function onMouseUp() {
  isDragging = false;
  document.removeEventListener("mousemove", onMouseMove);
  document.removeEventListener("mouseup", onMouseUp);

  // 关闭模糊效果
  blurEffect.classList.remove("active");

  // 拖动结束时挥动猫爪
  if (Math.random() > 0.5) {
    wavePaws();
  }
}

// 触摸设备支持
petContainer.addEventListener("touchstart", (e) => {
  // 如果正在自由移动，则停止
  if (isMovingFreely) {
    toggleFreeMovement();
  }

  e.preventDefault();
  const touch = e.touches[0];
  startX = touch.clientX;
  startY = touch.clientY;
  initialX = petContainer.offsetLeft;
  initialY = petContainer.offsetTop;

  isDragging = true;

  // 激活模糊效果
  blurEffect.classList.add("active");

  // 更新互动时间
  updateInteractionTime();
});

petContainer.addEventListener("touchmove", (e) => {
  if (!isDragging) return;
  e.preventDefault();

  const touch = e.touches[0];
  const newX = initialX + (touch.clientX - startX);
  const newY = initialY + (touch.clientY - startY);

  // 无边界移动
  const screenWidth = window.innerWidth;
  const screenHeight = window.innerHeight;

  const wrappedX = ((newX % screenWidth) + screenWidth) % screenWidth;
  const wrappedY = ((newY % screenHeight) + screenHeight) % screenHeight;

  petContainer.style.left = `${wrappedX}px`;
  petContainer.style.top = `${wrappedY}px`;

  // 如果控制面板是显示状态，更新它的位置
  if (controlPanel.classList.contains("show")) {
    const petRect = petContainer.getBoundingClientRect();
    controlPanel.style.left = `${petRect.left + petRect.width / 2}px`;
    controlPanel.style.top = `${petRect.bottom + 10}px`;
  }

  // 创建拖动粒子效果
  if (Math.random() > 0.7) {
    createDragParticles(touch.clientX, touch.clientY);
  }
});

petContainer.addEventListener("touchend", () => {
  isDragging = false;

  // 关闭模糊效果
  blurEffect.classList.remove("active");

  // 触摸结束时挥动猫爪
  if (Math.random() > 0.5) {
    wavePaws();
  }
});

// 随机动作
function randomAction() {
  // 如果不在自由移动状态，随机喵喵叫
  if (!isMovingFreely && Math.random() > 0.9) {
    const meows = ["喵~", "喵喵~", "喵？", "喵！", "喵..."];
    const randomMeow = meows[Math.floor(Math.random() * meows.length)];
    showNotification(randomMeow);
  }

  // 随机挥动猫爪
  if (!isMovingFreely && Math.random() > 0.8) {
    wavePaws();
  }

  // 随机摇尾巴
  if (!isMovingFreely && !isHungry && Math.random() > 0.7) {
    wagTail(true);
    setTimeout(() => {
      wagTail(false);
    }, 3000);
  }

  // 检查互动时间
  checkInteractionTime();
}

// 每隔一段时间随机执行动作
setInterval(randomAction, 30000);

// 初始化时的动画
setTimeout(() => {
  bounceCat();
  wavePaws();
  showNotification("喵~ 你好！");

  // 请求通知权限
  if (Notification.permission !== "granted" && Notification.permission !== "denied") {
    Notification.requestPermission();
  }
}, 1000);

// 窗口大小改变时，确保猫咪和控制面板在屏幕内
window.addEventListener("resize", () => {
  // 确保猫咪在屏幕内
  const maxX = window.innerWidth - petContainer.offsetWidth;
  const maxY = window.innerHeight - petContainer.offsetHeight;

  const currentX = Number.parseInt(petContainer.style.left) || 20;
  const currentY = Number.parseInt(petContainer.style.top) || 20;

  petContainer.style.left = `${Math.max(0, Math.min(currentX, maxX))}px`;
  petContainer.style.top = `${Math.max(0, Math.min(currentY, maxY))}px`;

  // 如果控制面板是显示状态，更新它的位置
  if (controlPanel.classList.contains("show")) {
    const petRect = petContainer.getBoundingClientRect();
    controlPanel.style.left = `${petRect.left + petRect.width / 2}px`;
    controlPanel.style.top = `${petRect.bottom + 10}px`;
  }
});

// 初始化手势识别
async function initHandGestureRecognition() {
  try {
    // 创建视频元素用于显示摄像头画面
    const videoElement = document.createElement("video");
    videoElement.width = 640;
    videoElement.height = 480;
    videoElement.style.display = "none";
    document.body.appendChild(videoElement);

    // 请求摄像头权限并启动视频流
    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
    videoElement.srcObject = stream;
    await videoElement.play();

    // 加载HandTrack.js模型
    const handTrackModel = await handTrack.load();
    startGestureDetection(videoElement, handTrackModel);
  } catch (error) {
    console.error("手势识别初始化失败:", error);
  }
}

// 开始手势检测
function startGestureDetection(videoElement, handTrackModel) {
  setInterval(async () => {
    if (videoElement && videoElement.readyState === 4) {
      const predictions = await handTrackModel.estimateHands(videoElement);
      if (predictions.length > 0) {
        const hand = predictions[0];
        // 检测食指勾一下的手势
        if (isIndexFingerHookGesture(hand)) {
          triggerVoiceResponse("你好啊主人");
        }
      }
    }
  }, 100);
}

// 食指勾一下手势检测逻辑
function isIndexFingerHookGesture(hand) {
  // 获取手指关键点
  const keypoints = hand.annotations.keypoints;
  const indexFingerTip = keypoints[handtrack.INDEX_FINGER_TIP];
  const indexFingerDIP = keypoints[handtrack.INDEX_FINGER_DIP];
  const indexFingerMCP = keypoints[handtrack.INDEX_FINGER_MCP];
  const middleFingerMCP = keypoints[handtrack.MIDDLE_FINGER_MCP];

  // 检查食指是否弯曲
  if (!indexFingerTip || !indexFingerDIP || !indexFingerMCP || !middleFingerMCP) {
    return false;
  }

  // 计算食指指尖到DIP的距离
  const indexFingerTipToDIPDistance = Math.sqrt(
    Math.pow(indexFingerTip[0] - indexFingerDIP[0], 2) +
    Math.pow(indexFingerTip[1] - indexFingerDIP[1], 2)
  );

  // 计算食指DIP到MCP的距离
  const indexFingerDIPToMCPDistance = Math.sqrt(
    Math.pow(indexFingerDIP[0] - indexFingerMCP[0], 2) +
    Math.pow(indexFingerDIP[1] - indexFingerMCP[1], 2)
  );

  // 计算食指MCP到中指MCP的距离（作为参考）
  const indexToMiddleMCPPDistance = Math.sqrt(
    Math.pow(indexFingerMCP[0] - middleFingerMCP[0], 2) +
    Math.pow(indexFingerMCP[1] - middleFingerMCP[1], 2)
  );

  // 判断食指是否弯曲（简化逻辑）
  if (indexFingerTipToDIPDistance < indexFingerDIPToMCPDistance * 0.5 && indexToMiddleMCPPDistance > 50) {
    return true;
  }

  return false;
}

// 触发语音回应
function triggerVoiceResponse(text) {
  if ("speechSynthesis" in window) {
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.1; // 设置语速
    utterance.pitch = 1.2; // 设置音调
    speechSynthesis.speak(utterance);
  }
}

// 初始化时启动手势识别
initHandGestureRecognition();