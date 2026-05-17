use anyhow::Context;
use crossbeam::channel::{self, Sender};
use image::{ImageBuffer, Rgb};
use pyo3::prelude::*;
use std::sync::{
    atomic::{AtomicBool, Ordering},
    Arc,
};
use std::thread;
use std::time::Duration;
use windows::{
    core::PCWSTR,
    Win32::Foundation::HWND,
    Win32::Graphics::Gdi::{
        CreateCompatibleBitmap, CreateCompatibleDC, DeleteDC, DeleteObject,
        GetDIBits, GetWindowDC, ReleaseDC, SelectObject, BITMAPINFO, BITMAPINFOHEADER,
        DIB_RGB_COLORS, RGBQUAD,
    },
    Win32::UI::WindowsAndMessaging::{
        GetClientRect, PrintWindow, PW_CLIENTONLY,
    },
};

// ---------- 颜色定义 (BGR 顺序：B, G, R) ----------
const COLOR_A_BGR: [u8; 3] = [0x2f, 0xd5, 0xb4];
const COLOR_B_BGR: [u8; 3] = [0xfe, 0xf4, 0x95];
const COLOR_TOLERANCE: i32 = 30;
const MIN_PIXELS: usize = 5;

// 基础 ROI (客户区坐标)
const ROI_BASE: (i32, i32, i32, i32) = (606, 64, 1319, 85);

/// 全局标题栏偏移量（可通过 Python 修改）
static mut TITLEBAR_OFFSET: i32 = 30;

fn roi_region() -> (i32, i32, i32, i32) {
    let off = unsafe { TITLEBAR_OFFSET };
    (ROI_BASE.0, ROI_BASE.1 + off, ROI_BASE.2, ROI_BASE.3 + off)
}

// ---------- PrintWindow 截图 ----------
fn capture_printwindow(hwnd: HWND) -> anyhow::Result<ImageBuffer<Rgb<u8>, Vec<u8>>> {
    let mut client_rect = windows::Win32::Foundation::RECT::default();
    unsafe { GetClientRect(hwnd, &mut client_rect)? };
    let width = client_rect.right - client_rect.left;
    let height = client_rect.bottom - client_rect.top;
    if width <= 0 || height <= 0 {
        anyhow::bail!("Invalid client area");
    }

    let hdc_window = unsafe { GetWindowDC(hwnd) };
    if hdc_window.is_invalid() {
        unsafe { ReleaseDC(hwnd, hdc_window) };
        anyhow::bail!("GetWindowDC failed");
    }
    let hdc_mem = unsafe { CreateCompatibleDC(hdc_window) };
    if hdc_mem.is_invalid() {
        unsafe { ReleaseDC(hwnd, hdc_window) };
        anyhow::bail!("CreateCompatibleDC failed");
    }

    let bitmap = unsafe { CreateCompatibleBitmap(hdc_window, width, height) };
    if bitmap.is_invalid() {
        unsafe {
            DeleteDC(hdc_mem);
            ReleaseDC(hwnd, hdc_window);
        }
        anyhow::bail!("CreateCompatibleBitmap failed");
    }

    let old_bitmap = unsafe { SelectObject(hdc_mem, bitmap) };

    let success = unsafe { PrintWindow(hwnd, hdc_mem, PW_CLIENTONLY.0 as u32) };
    if !success.as_bool() {
        unsafe {
            SelectObject(hdc_mem, old_bitmap);
            DeleteObject(bitmap);
            DeleteDC(hdc_mem);
            ReleaseDC(hwnd, hdc_window);
        }
        anyhow::bail!("PrintWindow failed");
    }

    let mut bmi = BITMAPINFO {
        bmiHeader: BITMAPINFOHEADER {
            biSize: std::mem::size_of::<BITMAPINFOHEADER>() as u32,
            biWidth: width,
            biHeight: -height, // 从上到下，BGR 顺序
            biPlanes: 1,
            biBitCount: 32,
            biCompression: 0,
            biSizeImage: 0,
            biXPelsPerMeter: 0,
            biYPelsPerMeter: 0,
            biClrUsed: 0,
            biClrImportant: 0,
        },
        bmiColors: [RGBQUAD::default(); 1],
    };
    let mut pixels = vec![0u8; (width * height * 4) as usize];

    let ret = unsafe {
        GetDIBits(
            hdc_window,
            bitmap,
            0,
            height as u32,
            Some(pixels.as_mut_ptr() as *mut _),
            &mut bmi,
            DIB_RGB_COLORS,
        )
    };
    if ret == 0 {
        anyhow::bail!("GetDIBits failed");
    }

    unsafe {
        SelectObject(hdc_mem, old_bitmap);
        DeleteObject(bitmap);
        DeleteDC(hdc_mem);
        ReleaseDC(hwnd, hdc_window);
    }

    // 转换 BGRX -> RGB Vec<u8>
    let mut rgb_pixels = Vec::with_capacity((width * height * 3) as usize);
    for chunk in pixels.chunks_exact(4) {
        let b = chunk[0];
        let g = chunk[1];
        let r = chunk[2];
        rgb_pixels.extend_from_slice(&[r, g, b]);
    }

    let img = ImageBuffer::<Rgb<u8>, _>::from_raw(width as u32, height as u32, rgb_pixels)
        .context("Failed to construct image from raw pixels")?;
    Ok(img)
}

// ---------- 颜色检测 ----------
fn detect_color_rect(
    roi_img: &ImageBuffer<Rgb<u8>, Vec<u8>>,
    target_bgr: &[u8; 3],
    tolerance: i32,
    min_pixels: usize,
) -> (usize, Option<(u32, u32, u32, u32)>) {
    let t_r = target_bgr[2] as i32;
    let t_g = target_bgr[1] as i32;
    let t_b = target_bgr[0] as i32;

    let mut count = 0;
    let mut min_x = u32::MAX;
    let mut min_y = u32::MAX;
    let mut max_x = 0u32;
    let mut max_y = 0u32;

    for (x, y, pixel) in roi_img.enumerate_pixels() {
        let r = pixel[0] as i32;
        let g = pixel[1] as i32;
        let b = pixel[2] as i32;
        if (r - t_r).abs() <= tolerance
            && (g - t_g).abs() <= tolerance
            && (b - t_b).abs() <= tolerance
        {
            count += 1;
            min_x = min_x.min(x);
            min_y = min_y.min(y);
            max_x = max_x.max(x);
            max_y = max_y.max(y);
        }
    }

    if count < min_pixels {
        return (count, None);
    }
    (count, Some((min_x, min_y, max_x + 1, max_y + 1)))
}

// ---------- 检测线程的消息 ----------
#[derive(Debug, Clone)]
enum DetectionMsg {
    A {
        pixels: usize,
        rect: Option<(u32, u32, u32, u32)>,
    },
    B {
        pixels: usize,
        rect: Option<(u32, u32, u32, u32)>,
    },
}

fn worker_loop(
    hwnd: HWND,
    target_bgr: &'static [u8; 3],
    sender: Sender<DetectionMsg>,
    running: Arc<AtomicBool>,
    color_tag: DetectionMsg,
) {
    let roi = roi_region();
    while running.load(Ordering::Acquire) {
        let full_img = match capture_printwindow(hwnd) {
            Ok(img) => img,
            Err(e) => {
                eprintln!("Screenshot error: {e}");
                thread::sleep(Duration::from_millis(10));
                continue;
            }
        };

        let (rx1, ry1, rx2, ry2) = roi;
        let (w, h) = full_img.dimensions();
        let rx1 = (rx1.max(0) as u32).min(w);
        let ry1 = (ry1.max(0) as u32).min(h);
        let rx2 = (rx2.max(1) as u32).min(w);
        let ry2 = (ry2.max(1) as u32).min(h);
        if rx2 <= rx1 || ry2 <= ry1 {
            thread::sleep(Duration::from_millis(5));
            continue;
        }
        let roi_img = full_img.view(rx1, ry1, rx2 - rx1, ry2 - ry1).to_image();

        let (pixels, rect) = detect_color_rect(&roi_img, target_bgr, COLOR_TOLERANCE, MIN_PIXELS);

        let msg = match &color_tag {
            DetectionMsg::A { .. } => DetectionMsg::A { pixels, rect },
            DetectionMsg::B { .. } => DetectionMsg::B { pixels, rect },
            _ => unreachable!(),
        };
        if sender.send(msg).is_err() {
            break;
        }

        thread::sleep(Duration::from_millis(5));
    }
}

// ---------- 核心结构（内部 Rust 实现）----------
struct FishingRoiCoreInner {
    running: Arc<AtomicBool>,
    handles: Option<(thread::JoinHandle<()>, thread::JoinHandle<()>)>,
    receiver: crossbeam::channel::Receiver<DetectionMsg>,
    last_a: (usize, Option<(u32, u32, u32, u32)>),
    last_b: (usize, Option<(u32, u32, u32, u32)>),
}

impl FishingRoiCoreInner {
    fn new(hwnd: HWND) -> Self {
        let (tx, rx) = channel::unbounded();
        let running = Arc::new(AtomicBool::new(false));

        let tx_a = tx.clone();
        let tx_b = tx;
        let running_a = Arc::clone(&running);
        let running_b = Arc::clone(&running);

        let t1 = thread::spawn(move || {
            worker_loop(
                hwnd,
                &COLOR_A_BGR,
                tx_a,
                running_a,
                DetectionMsg::A { pixels: 0, rect: None },
            )
        });
        let t2 = thread::spawn(move || {
            worker_loop(
                hwnd,
                &COLOR_B_BGR,
                tx_b,
                running_b,
                DetectionMsg::B { pixels: 0, rect: None },
            )
        });

        Self {
            running,
            handles: Some((t1, t2)),
            receiver: rx,
            last_a: (0, None),
            last_b: (0, None),
        }
    }

    fn start(&mut self) {
        self.running.store(true, Ordering::Release);
    }

    fn stop(&mut self) {
        self.running.store(false, Ordering::Release);
        if let Some((t1, t2)) = self.handles.take() {
            let _ = t1.join();
            let _ = t2.join();
        }
    }

    fn update(&mut self) {
        while let Ok(msg) = self.receiver.try_recv() {
            match msg {
                DetectionMsg::A { pixels, rect } => self.last_a = (pixels, rect),
                DetectionMsg::B { pixels, rect } => self.last_b = (pixels, rect),
            }
        }
    }

    fn get_data(&self) -> (usize, Option<(u32,u32,u32,u32)>, usize, Option<(u32,u32,u32,u32)>) {
        (self.last_a.0, self.last_a.1, self.last_b.0, self.last_b.1)
    }
}

// ---------- PyO3 包装类（暴露给 Python）----------
#[pyclass]
struct FishingRoiCore {
    inner: Option<FishingRoiCoreInner>,   // Option 允许在 drop 时先停止
}

#[pymethods]
impl FishingRoiCore {
    /// 创建实例，传入窗口句柄整数
    #[new]
    fn new(hwnd: isize) -> PyResult<Self> {
        if hwnd == 0 {
            return Err(pyo3::exceptions::PyValueError::new_err("无效的窗口句柄"));
        }
        let inner = FishingRoiCoreInner::new(HWND(hwnd));
        Ok(Self { inner: Some(inner) })
    }

    /// 启动检测线程
    fn start(&mut self) {
        if let Some(ref mut inner) = self.inner {
            inner.start();
        }
    }

    /// 停止检测线程
    fn stop(&mut self) {
        if let Some(ref mut inner) = self.inner {
            inner.stop();
        }
    }

    /// 消费内部消息并更新最新数据
    fn update(&mut self) {
        if let Some(ref mut inner) = self.inner {
            inner.update();
        }
    }

    /// 获取当前检测结果，返回元组:
    /// (pixels_a, (x1,y1,x2,y2) or None, pixels_b, (x1,y1,x2,y2) or None)
    fn get_data(&mut self) -> PyResult<(usize, Option<(u32,u32,u32,u32)>, usize, Option<(u32,u32,u32,u32)>)> {
        // 先更新再返回最新数据
        self.update();
        match self.inner {
            Some(ref inner) => Ok(inner.get_data()),
            None => Err(pyo3::exceptions::PyRuntimeError::new_err("Core 已停止")),
        }
    }
}

// ---------- 模块定义 ----------
#[pymodule]
fn roi_rust_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<FishingRoiCore>()?;
    Ok(())
}