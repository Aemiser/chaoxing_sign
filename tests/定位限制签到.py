"""
给定三个已知经纬度点，以及它们各自到目标点的地面距离，
计算目标点的经纬度。

两个点给出两个候选解，第三个点用于消歧得到唯一解。

参数填下面：
"""
import math

# ============================================================
# 参数区 —— 修改这里
# ============================================================
POINT_A = (23.336505, 113.747669)   # 点A (纬度, 经度)
POINT_B = (23.505136, 113.351021)   # 点B (纬度, 经度)
POINT_C = (22.72455, 113.271828)   # 点C (纬度, 经度)，用于消歧
DIST_A  = 18013.0                 # 点A到目标点的地面距离（米）
DIST_B  = 31274.0                 # 点B到目标点的地面距离（米）
DIST_C  = 72100.0                 # 点C到目标点的地面距离（米）

EARTH_RADIUS = 6371000.0        # 地球半径（米），可按需调整
# ============================================================


def _latlon_to_xy(ref_lat, ref_lon, lat, lon):
    """以 ref 为原点，将 (lat,lon) 转为局部平面坐标 (east, north) 米"""
    dlat = math.radians(lat - ref_lat)
    dlon = math.radians(lon - ref_lon)
    avg_lat = math.radians((ref_lat + lat) / 2)
    east = EARTH_RADIUS * dlon * math.cos(avg_lat)
    north = EARTH_RADIUS * dlat
    return east, north


def _xy_to_latlon(ref_lat, ref_lon, east, north):
    """局部平面坐标 (east, north) 米 → (lat, lon)"""
    lat = ref_lat + math.degrees(north / EARTH_RADIUS)
    avg_lat = math.radians((ref_lat + lat) / 2)
    lon = ref_lon + math.degrees(east / (EARTH_RADIUS * math.cos(avg_lat)))
    return lat, lon


def _haversine(lat_a, lon_a, lat_b, lon_b):
    """两点间地面距离（米）"""
    dlat = math.radians(lat_b - lat_a)
    dlon = math.radians(lon_b - lon_a)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat_a)) * math.cos(math.radians(lat_b))
         * math.sin(dlon / 2) ** 2)
    return EARTH_RADIUS * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def solve_two(lat1, lon1, d1, lat2, lon2, d2):
    """
    A、B 两个点求交点（生成器，0~2 个候选解）。

    参数
    ----
    lat1, lon1 : 点A 纬度/经度（度）
    lat2, lon2 : 点B 纬度/经度（度）
    d1, d2     : A/B 到目标的地面距离（米）

    返回
    ----
    yield (lat, lon) — 候选目标点
    """
    bx, by = _latlon_to_xy(lat1, lon1, lat2, lon2)

    d_ab_sq = bx * bx + by * by
    if d_ab_sq < 1e-15:
        return

    rhs = (d1 * d1 - d2 * d2 + d_ab_sq) / 2
    scale = rhs / d_ab_sq

    px = scale * bx
    py = scale * by

    h_sq = d1 * d1 - (px * px + py * py)

    if h_sq < 0:
        if h_sq > -1e-9:
            h_sq = 0.0
        else:
            return

    h = math.sqrt(h_sq)
    d_ab = math.sqrt(d_ab_sq)
    ux, uy = bx / d_ab, by / d_ab

    for sign in (+1, -1):
        ex = px + sign * h * (-uy)
        ey = py + sign * h * ux
        yield _xy_to_latlon(lat1, lon1, ex, ey)


def solve_three(lat1, lon1, d1, lat2, lon2, d2, lat3, lon3, d3):
    """
    三个点求唯一交点。

    先用 A、B 得到候选解，再用 C 的距离消歧。

    返回
    ----
    (lat, lon) — 唯一目标坐标，无解时返回 None
    """
    candidates = list(solve_two(lat1, lon1, d1, lat2, lon2, d2))

    if not candidates:
        return None

    if len(candidates) == 1:
        return candidates[0]

    best = None
    best_err = float("inf")
    for lat, lon in candidates:
        err = abs(_haversine(lat3, lon3, lat, lon) - d3)
        if err < best_err:
            best_err = err
            best = (lat, lon)

    return best


if __name__ == "__main__":
    result = solve_three(
        POINT_A[0], POINT_A[1], DIST_A,
        POINT_B[0], POINT_B[1], DIST_B,
        POINT_C[0], POINT_C[1], DIST_C,
    )

    print(f"点A: {POINT_A}  距离目标: {DIST_A} m")
    print(f"点B: {POINT_B}  距离目标: {DIST_B} m")
    print(f"点C: {POINT_C}  距离目标: {DIST_C} m")

    if result is None:
        print("\n无解（圆无交点或数据矛盾）")
    else:
        lat, lon = result
        print(f"\n目标: lat={lat:.6f}, lon={lon:.6f}")

        # 验算
        print()
        for name, (plat, plon), d in [
            ("A", POINT_A, DIST_A),
            ("B", POINT_B, DIST_B),
            ("C", POINT_C, DIST_C),
        ]:
            calc = _haversine(plat, plon, lat, lon)
            delta = calc - d
            print(f"  到{name}: {calc:.2f}m  (偏差 {delta:+.2f}m)")
