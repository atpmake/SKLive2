# ラズパイ移植 test10
import cv2
import numpy as np
import time
import requests
import pandas as pd
import matplotlib.pyplot as plt
import tkinter as tk
from collections import namedtuple

# 矩形情報を扱うための構造体を定義
Rect = namedtuple('Rect', ['x', 'y', 'w', 'h'])
# グローバル変数をオブジェクト形式で初期化
area_a = Rect(0, 0, 0, 0)
area_b = Rect(0, 0, 0, 0)
area_c = Rect(0, 0, 0, 0)

running = True

def detect_areas(img):
    global area_a, area_b, area_c
    if img is None: return False
    h,w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # --- 1. area_a (側面) 検出 ---
    # scan_x_start, scan_x_end = 100, 1500
    # search_y_start, search_y_end = 300, 750
    scan_x_start, scan_x_end = 10, w - 10
    search_y_start, search_y_end = int(h * 0.3), int(h * 0.7)
    threshold_line = 150
    y_scores = [np.mean(gray[y, scan_x_start:scan_x_end]) for y in range(search_y_start, search_y_end)]
    line_indices = [i + search_y_start for i in range(1, len(y_scores)-1) 
                    if y_scores[i] > threshold_line and y_scores[i] >= y_scores[i-1] and y_scores[i] >= y_scores[i+1]]
    if len(line_indices) < 2: return False
    a_top_y, a_bottom_y = int(line_indices[0]), int(line_indices[-1])
    white_indices = np.where(gray[a_top_y, :] > threshold_line)[0]
    if len(white_indices) == 0: return False
    a_left_x, a_right_x = int(white_indices[0]), int(white_indices[-1])
    area_a = Rect(a_left_x, a_top_y, a_right_x - a_left_x, a_bottom_y - a_top_y)

    # --- 2. area_b (上面) 検出 ---
    # t_search_x_start, t_search_x_end = 400, 900
    t_search_x_start, t_search_x_end = int(w * 0.3), int(w * 0.66) #2026/4/29
    threshold_white = 220
    b_top_y = next((y for y in range(5, area_a.y) if np.sum(gray[y, t_search_x_start:t_search_x_end] > threshold_white) > 10), None)
    if b_top_y is not None:
        b_roi = gray[b_top_y:area_a.y, t_search_x_start:t_search_x_end]
        b_pts = np.where(b_roi > threshold_white)
        b_left_x = int(np.min(b_pts[1])) + t_search_x_start
        b_right_x = int(np.max(b_pts[1])) + t_search_x_start
        area_b = Rect(b_left_x, b_top_y, b_right_x - b_left_x, area_a.y - b_top_y)
    
    # --- 3. area_c (底面) 設定 ---
    area_c = Rect(area_b.x, area_a.y + area_a.h, area_b.w, area_b.h)
    return True

def check_pmt_activity(img):
    roi = img[area_a.y : area_a.y + area_a.h, area_a.x : area_a.x + area_a.w]
    hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    _, pmt_mask = cv2.threshold(hsv_roi[:, :, 1], 50, 255, cv2.THRESH_BINARY)
    density = (cv2.countNonZero(pmt_mask) / (area_a.w * area_a.h)) * 100
    return density

def extract_all_pmts(img):
    """
    Area A, B, C 全てから格子座標を抽出し、一つのリストにまとめる
    """
    all_pmts = []
    # ターゲット設定：(エリア名, Rectオブジェクト)
    targets = [('A', area_a), ('B', area_b), ('C', area_c)]

    print(f"\n--- Full PMT Mapping (A, B, C) ---")

    for label, rect in targets:
        # エリアが未検出（0,0,0,0）の場合はスキップ
        if rect.w == 0 or rect.h == 0: continue

        # 1. エリアの切り出しと二値化
        roi = img[rect.y : rect.y + rect.h, rect.x : rect.x + rect.w]
        hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        _, mask = cv2.threshold(hsv_roi[:, :, 1], 50, 255, cv2.THRESH_BINARY)

        # 2. ブロブ解析で「存在するドット」の座標を拾う
        num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(mask)
        
        raw_x = []
        raw_y = []
        for i in range(1, num_labels):
            if 5 <= stats[i, cv2.CC_STAT_AREA] <= 15:
                cx, cy = centroids[i]
                raw_x.append(int(round(cx)))
                raw_y.append(int(round(cy)))

        if not raw_x or not raw_y:
            print(f"  Area {label}: No PMTs detected.")
            continue

        # 3. 格子（グリッド）の再構築
        # 重複を排除してソートしたユニークなX, Yの組み合わせ
        unique_x = sorted(list(set(raw_x)))
        unique_y = sorted(list(set(raw_y)))

        count_in_area = 0
        for uy in unique_y:
            for ux in unique_x:
                abs_x = ux + rect.x
                abs_y = uy + rect.y
                # リスト形式: (エリア名, x座標, y座標)
                all_pmts.append((label, abs_x, abs_y))
                count_in_area += 1
        
        print(f"  Area {label}: {count_in_area} pts ({len(unique_x)}x{len(unique_y)})")
    
    return all_pmts

def save_plots_csv(pmt_list, filename='plots2.csv'):
    """
    以前の形式に合わせて保存: area, x, y
    """
    with open(filename, 'w') as f:
        f.write("area,x,y\n")
        for label, x, y in pmt_list:
            f.write(f"{label},{x},{y}\n")
    print(f"\nSuccessfully saved {len(pmt_list)} PMTs to {filename}")

def fetch_image_data(url):
    resp = requests.get(url)
    if resp.status_code == 200:
        arr = np.frombuffer(resp.content, np.uint8)
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return None

def prepare_learned_image(target_url, threshold_density=8.0, max_retry=5):
    # ---- 待ち時間のメッセージBOX ----
    msg_box = tk.Tk()
    msg_box.title("Super-K Monitor")
    msg_box.attributes("-topmost", True)  
    label = tk.Label(msg_box, text="\n PMT座標を抽出しています...\n しばらくお待ちください\n", 
                     padx=20, pady=10, font=("Helvetica", 14))
    label.pack()
    msg_box.update() # ここで一旦画面に表示させる

    learned_img = None
    for i in range(max_retry):
        print(f"\n[Learning Mode] Step {i+1}/{max_retry}")
        new_img = fetch_image_data(target_url)
        if new_img is None: continue
        if i == 0:
            if not detect_areas(new_img): return None
            learned_img = new_img
        else:
            learned_img = cv2.max(learned_img, new_img)
        
        # cv2.imshow("Learning Process", cv2.resize(learned_img, None, fx=0.5, fy=0.5))
        cv2.waitKey(1)
        density = check_pmt_activity(learned_img)
        print(f"  Current Density: {density:.2f}%")
        if density >= threshold_density: 
            break
        else:
            print("  wait next images...")

        if i < max_retry - 1: 
            wait_start = time.time()
            while (time.time() - wait_start) < 15 :
                msg_box.update()
                time.sleep(0.1)
    cv2.destroyAllWindows()
    msg_box.destroy()
    return learned_img

def on_click(event):
    global running
    touch_x = event.x; touch_y = event.y
    # print(touch_x, touch_y)
    exit_area_size = 50
    if touch_x < exit_area_size and touch_y > (800 - exit_area_size):
        running = False
        print("\n左上がタッチされました。終了します...")

def run_sk_realtime_monitor(csv_file='plots2.csv',url=''):
    global running
    
    # --- STEP 1: 初期設定 ---
    try:
        # csv内の列名は area, x, y (test08の出力)
        df = pd.read_csv(csv_file)
        print(f"CSV読み込み完了: {len(df)} 点")
    except Exception as e:
        print(f"CSV読み込みエラー: {e}")
        return

    # エリア範囲の自動計算 (マッピング用)
    bounds = {}
    for area in ['A', 'B', 'C']:
        area_data = df[df['area'] == area]
        if not area_data.empty:
            bounds[area] = {
                'xmin': area_data['x'].min(), 'xmax': area_data['x'].max(),
                'ymin': area_data['y'].min(), 'ymax': area_data['y'].max()
            }

    # 3Dマッピングの事前計算 (offset_rad等、以前の調整値を反映)
    offset_rad = np.pi / 2 
    master_pmt_list = []
    for _, row in df.iterrows():
        area = row['area']
        px, py = int(row['x']), int(row['y'])
        b = bounds.get(area)
        if not b: continue

        if area == 'A':
            theta = ((px - b['xmin']) / (b['xmax'] - b['xmin'])) * 2 * np.pi + offset_rad
            z_3d = 1.0 - ((py - b['ymin']) / (b['ymax'] - b['ymin']))
            x_3d, y_3d = 0.5 * np.cos(theta), 0.5 * np.sin(theta)
        elif area == 'B': # 天井
            x_3d = ((px - b['xmin']) / (b['xmax'] - b['xmin'])) - 0.5   
            x_3d = x_3d * 0.95
            y_3d = ((b['ymax'] - py) / (b['ymax'] - b['ymin'])) - 0.5   
            y_3d = y_3d * 0.95
            z_3d = 1.0
        elif area == 'C': # 底面
            x_3d = ((px - b['xmin']) / (b['xmax'] - b['xmin'])) - 0.5   
            x_3d = x_3d * 0.95
            y_3d = ((py - b['ymin']) / (b['ymax'] - b['ymin'])) - 0.5  
            y_3d = y_3d * 0.95 
            z_3d = 0.0
            
        master_pmt_list.append({'3d': (x_3d, y_3d, z_3d), 'img': (px, py)})

    # --- STEP 2: 描画ウィンドウの準備 (ラズパイ用設定) ---
    plt.ion()
    plt.rcParams['toolbar'] = 'None'    # RP ツールバー非表示 

    fig = plt.figure(figsize=(4.8,8.0), facecolor='black', dpi=100) # RP 画面いっぱいに
    ax3d = fig.add_subplot(111, projection='3d')
    ax3d.set_facecolor('black')
    ax3d.axis('off')
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    mng = plt.get_current_fig_manager()
    try:
        # mng.full_screen_toggle()
        mng.window.overrideredirect(True)
        mng.window.geometry("480x800+0+0")
    except:
        mng.full_screen_toggle()
        pass

    plt.show()
    plt.pause(0.1)
    
    url = "https://www-sk.icrr.u-tokyo.ac.jp/realtimemonitor/skev.gif"
    print("Windowsモードでリアルタイムモニタを開始します...")
    fig.canvas.mpl_connect('button_press_event', on_click)

    # --- STEP 3: 観測メインループ ---
    try:
        while running:
            # 最新画像をRGBモードで取得 (色味を維持)
            try:
                resp = requests.get(url, timeout=5)
                arr = np.frombuffer(resp.content, np.uint8)
                img_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            except Exception as e:
                print(f"画像取得エラー: {e}")
                plt.pause(2.0)
                continue

            # ヒット情報の抽出 (RGB直結)
            final_x, final_y, final_z, final_colors = [], [], [], []
            for pmt in master_pmt_list:
                px, py = pmt['img']
                r, g, b = img_rgb[py, px]
                
                # 黒(背景)と白(文字等)を除外
                if (r, g, b) != (0, 0, 0) and (r, g, b) != (255, 255, 255):
                    x, y, z = pmt['3d']
                    # 以前の奥行きによる透過度計算
                    depth = (y - (-0.5)) / 1.0
                    alpha = max(0.2, 0.9 - depth * 0.2) # 0.7
                    final_colors.append((r/255, g/255, b/255, alpha))
                    final_x.append(x); final_y.append(y); final_z.append(z)

            # プロット更新
            ax3d.cla()
            ax3d.set_facecolor('black')
            
            # 円柱エッジ描画
            edge_theta = np.linspace(0, 2 * np.pi, 100)
            ex, ey = 0.5 * np.cos(edge_theta), 0.5 * np.sin(edge_theta)
            ax3d.plot(ex, ey, 1.0, color='white', linewidth=0.5, alpha=0.5) # 天井
            ax3d.plot(ex, ey, 0.0, color='white', linewidth=0.5, alpha=0.5) # 底面
            
            # 垂直補助線 (0度, 180度)
            for deg in [0, 180]:
                rad = np.radians(deg)
                vx, vy = 0.5 * np.cos(rad), 0.5 * np.sin(rad)
                ax3d.plot([vx, vx], [vy, vy], [0.0, 1.0], color='white', linewidth=0.5, alpha=0.5)

            # ヒットがあれば描画
            if final_x:
                # 奥行きによるサイズ調整
                sizes = 6 * (1.0 - (np.array(final_y) - (-0.5)) * 0.2) # 0.4
                ax3d.scatter(final_x, final_y, final_z, c=final_colors, s=sizes, edgecolors='none', marker='o')

            # 表示設定
            ax3d.set_box_aspect((1, 1, 1))
            ax3d.set_proj_type('ortho')
            zoom = 0.7
            ax3d.set_xlim(-0.5 * zoom, 0.5 * zoom)
            ax3d.set_ylim(-0.5 * zoom, 0.5 * zoom)
            ax3d.set_zlim(0, 0.95)    # -0.1, 1.1
            ax3d.axis('off')
            ax3d.view_init(elev=20, azim=-90)
            
            plt.title(f"Super-Kamiokande Live\n {time.strftime('%H:%M:%S')}", color='white', fontsize=20, pad=0)
            plt.draw()
            
            # --- インターバル待機 (タイマー方式) ---
            update_interval = 9.5 
            start_wait_time = time.time()
            while (time.time() - start_wait_time) < update_interval:
                if not running: break
                # plt.pause(0.1) # GUIイベントを処理しつつ待機
                fig.canvas.flush_events()
                time.sleep(0.1)
                
    except KeyboardInterrupt:
        print("\n停止します。")
    except Exception as e:
        # それ以外の予期せぬエラー時
        print(f"エラー発生: {e}")
    finally:
        plt.close('all')


# ********** main **********
if __name__ == '__main__':
    URL = "https://www-sk.icrr.u-tokyo.ac.jp/realtimemonitor/skev.gif"
    final_img = prepare_learned_image(URL, threshold_density=5.0)
    
    if final_img is not None:
        pmt_coords = extract_all_pmts(final_img)
        if pmt_coords:
            save_plots_csv(pmt_coords, filename='plots2.csv')

        run_sk_realtime_monitor(csv_file='plots2.csv', url=URL)     
