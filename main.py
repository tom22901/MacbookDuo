import sys
import math
import numpy as np
import cv2
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QRect
from PyQt5.QtWidgets import QApplication, QWidget, QLabel
from PyQt5.QtGui import QImage, QPixmap
from pybooklid import LidSensor


# 1. 传感器监听线程（高频采样）
class SensorThread(QThread):
    angle_changed = pyqtSignal(float)

    def run(self):
        try:
            with LidSensor() as sensor:
                for angle in sensor.monitor(interval=0.016):  # 约 60Hz 采样
                    self.angle_changed.emit(angle)
        except Exception as e:
            print(f"传感器错误: {e}")


# 2. 具有景深透视拉伸效果的窗口
class PerspectiveFlipOverlay(QWidget):
    def __init__(self):
        super().__init__()

        # 获取屏幕逻辑分辨率
        screen = QApplication.primaryScreen()
        self.screen_rect = screen.geometry()
        self.w = self.screen_rect.width()
        self.h = self.screen_rect.height()

        # 抓取当前屏幕内容
        q_content_pixmap = screen.grabWindow(0)
        self.content_np = self.qpixmap_to_numpy(q_content_pixmap)

        # [核心修复] 如果物理截图尺寸与逻辑分辨率不一致，缩放到逻辑分辨率
        if self.content_np.shape[1] != self.w or self.content_np.shape[0] != self.h:
            self.content_np = cv2.resize(self.content_np, (self.w, self.h), interpolation=cv2.INTER_AREA)

        # 预计算：原始内容的四个角点
        self.src_points = np.float32([
            [0, 0],  # 左上
            [self.w, 0],  # 右上
            [self.w, self.h],  # 右下
            [0, self.h]  # 左下
        ])

        # 窗口属性：无边框、置顶
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(0, 0, self.w, self.h)

        # 用于承载图像的标签
        self.image_label = QLabel(self)
        self.image_label.resize(self.w, self.h)

        self.show()

    def qpixmap_to_numpy(self, pixmap):
        """将 PyQt Pixmap 转换为 OpenCV numpy 格式"""
        qimage = pixmap.toImage()
        qimage = qimage.convertToFormat(QImage.Format_RGB888)
        width = qimage.width()
        height = qimage.height()
        ptr = qimage.bits()
        ptr.setsize(height * width * 3)
        arr = np.frombuffer(ptr, np.uint8).reshape((height, width, 3))
        return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

    def update_perspective_by_angle(self, angle):
        """根据角度，计算透视变换并更新画面"""
        MAX_ANGLE = 130.0
        MIN_ANGLE = 0.0
        clamped_angle = max(MIN_ANGLE, min(angle, MAX_ANGLE))

        # 1. 计算归一化的比例因子 (0.0 到 1.0)
        ratio = (clamped_angle - MIN_ANGLE) / (MAX_ANGLE - MIN_ANGLE)
        close_progress = 1.0 - ratio  # 屏幕合上的程度：0(完全打开) -> 1(完全合上)

        # ==================== 修改：彻底蔓延至屏幕底部的全黑/全模糊 ====================
        processed_img = self.content_np.copy()

        if close_progress > 0.01:
            # 1. 蔓延前沿位置 (从 0 到 1.2 * h，多出的 0.2 确保最后完全推过底部)
            # 调整 SPREAD_EXPONENT 可改变蔓延速度响应
            SPREAD_EXPONENT = 1.2
            progress_factor = np.power(close_progress, SPREAD_EXPONENT)

            # 前沿位置：随着 close_progress 增加，从 top 推进到超过 bottom
            front_y = self.h * 1.25 * progress_factor

            # 渐变过渡带的长度（像素数），数值越小，蔓延边缘越硬；数值越大，过渡越平滑
            FADE_LENGTH = self.h * 0.3

            # 2. 生成纵向 Mask：在 front_y 以上为 1.0，向下逐渐过渡到 0.0
            y_indices = np.arange(self.h, dtype=np.float32)[:, np.newaxis]

            # 计算距离前沿的位置并归一化
            mask = np.clip((front_y - y_indices) / FADE_LENGTH, 0.0, 1.0)
            mask = np.power(mask, 1.2)  # 边缘平滑度
            mask_3ch = np.repeat(mask[:, :, np.newaxis], 3, axis=2)

            # 3. 高斯模糊图层 (随着合盖，全局最大模糊度同步提升)
            max_kernel = int(15 + 65 * close_progress)
            if max_kernel % 2 == 0: max_kernel += 1
            blurred_img = cv2.GaussianBlur(self.content_np, (max_kernel, max_kernel), 0)

            # 4. 生成黑色图层
            black_img = np.zeros_like(self.content_np)

            # 5. 双重混合：先将原图与模糊混合，再将前沿推过的部分彻底推向纯黑
            # 随着 close_progress 接近 1，黑色的强度逐步拉满到 1.0
            black_intensity = np.clip(close_progress * 1.3, 0.0, 1.0)

            # 混合模糊
            img_blurred = (blurred_img * mask_3ch + self.content_np * (1.0 - mask_3ch))
            # 混合纯黑（前沿推过的地方变黑）
            final_mask = mask_3ch * black_intensity
            processed_img = (black_img * final_mask + img_blurred * (1.0 - final_mask)).astype(np.uint8)
        # ====================================================================

        # 2. 透视变换计算（使用带有黑色渐变效果的 processed_img）
        min_top_ratio = 0.3
        top_width_ratio = min_top_ratio + (1.0 - min_top_ratio) * ratio

        dst_p1_bottom_left = [0, self.h]
        dst_p2_bottom_right = [self.w, self.h]

        top_w = self.w * top_width_ratio
        margin_x = (self.w - top_w) / 2.0

        dst_p0_top_left = [margin_x, 0]
        dst_p3_top_right = [self.w - margin_x, 0]

        dst_points = np.float32([
            dst_p0_top_left,  # 左上
            dst_p3_top_right,  # 右上
            dst_p2_bottom_right,  # 右下
            dst_p1_bottom_left  # 左下
        ])

        # --- 使用 OpenCV 进行图像变换 ---
        matrix = cv2.getPerspectiveTransform(self.src_points, dst_points)

        warped_img = cv2.warpPerspective(
            processed_img, matrix, (self.w, self.h),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0)  # 梯形之外填充黑色
        )

        # --- 将 OpenCV 图像显示到 PyQt Label ---
        warped_img_rgb = cv2.cvtColor(warped_img, cv2.COLOR_BGR2RGB)
        h, w, c = warped_img_rgb.shape
        qimage = QImage(warped_img_rgb.data, w, h, w * c, QImage.Format_RGB888)
        self.image_label.setPixmap(QPixmap.fromImage(qimage))


if __name__ == "__main__":
    app = QApplication(sys.argv)

    overlay = PerspectiveFlipOverlay()

    sensor_thread = SensorThread()
    sensor_thread.angle_changed.connect(overlay.update_perspective_by_angle)
    sensor_thread.start()

    sys.exit(app.exec_())