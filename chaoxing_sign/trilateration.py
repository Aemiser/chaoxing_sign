"""三角定位工具 — 根据三组已知坐标及其到目标点的距离推算目标经纬度"""
from __future__ import annotations
import math

EARTH_RADIUS = 6371000.0


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
    """A、B 两个点求交点（生成器，0~2 个候选解）"""
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
    """三个点求唯一交点。

    先用 A、B 得到候选解，再用 C 的距离消歧。

    Returns:
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


def solve_gn(probes: list[tuple[float, float, float]],
             init_lat: float, init_lon: float,
             max_iter: int = 10) -> tuple[float, float]:
    """Gauss-Newton 球面非线性最小二乘求解目标坐标。

    利用所有探测点的 (lat, lon, distance) 一次性拟合，球面上二次收敛，
    通常 3~5 次内部迭代即可收敛到米级精度。

    probes : [(lat, lon, distance_meters), ...]
    init_lat, init_lon : 初始猜测（度）
    """
    import math
    R = EARTH_RADIUS
    lat = math.radians(init_lat)
    lon = math.radians(init_lon)

    for _ in range(max_iter):
        cos_lat = math.cos(lat)
        sin_lat = math.sin(lat)

        a11 = a12 = a22 = 0.0
        b1 = b2 = 0.0
        n_used = 0

        for plat_d, plon_d, dist in probes:
            plat = math.radians(plat_d)
            plon = math.radians(plon_d)
            cos_plat = math.cos(plat)

            # 球面距离
            dlat = lat - plat
            dlon = lon - plon
            hav = math.sin(dlat / 2) ** 2 + cos_plat * cos_lat * math.sin(dlon / 2) ** 2
            hav = min(hav, 1.0)
            est = R * 2 * math.asin(math.sqrt(hav))

            sin_c = math.sin(est / R)
            if sin_c < 1e-10:
                continue

            cos_c = math.cos(est / R)

            # 从 guess 到 probe 的方位角
            cos_az = (math.sin(plat) - sin_lat * cos_c) / (cos_lat * sin_c)
            sin_az = math.sin(plon - lon) * cos_plat / sin_c
            cos_az = max(-1.0, min(1.0, cos_az))
            sin_az = max(-1.0, min(1.0, sin_az))

            # ∂d/∂lat_rad = -R * cos(az)
            # ∂d/∂lon_rad = -R * sin(az) * cos(lat)
            jlat = -R * cos_az
            jlon = -R * sin_az * cos_lat
            resid = est - dist

            a11 += jlat * jlat
            a12 += jlat * jlon
            a22 += jlon * jlon
            b1  += jlat * resid
            b2  += jlon * resid
            n_used += 1

        if n_used < 2:
            break

        # 2×2 求解 Δ = -inv(J^T J) * (J^T r)
        det = a11 * a22 - a12 * a12
        if abs(det) < 1e-20:
            break
        dlat = -(b1 * a22 - b2 * a12) / det
        dlon = -(b2 * a11 - b1 * a12) / det

        # 步长限制：单步 ≤ 1° ≈ 111 km（防发散）
        max_step = math.radians(1.0)
        step = math.hypot(dlat, dlon)
        if step > max_step:
            dlat *= max_step / step
            dlon *= max_step / step

        lat += dlat
        lon += dlon

        if abs(dlat * R) < 1.0 and abs(dlon * R * cos_lat) < 1.0:
            break

    return math.degrees(lat), math.degrees(lon)
