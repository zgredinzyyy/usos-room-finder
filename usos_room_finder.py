import os
import re
import argparse
import urllib.request
import http.cookiejar
import time
import sys
import threading
from datetime import datetime, timedelta
from html.parser import HTMLParser

class Spinner:
    def __init__(self, message="Pobieranie danych..."):
        self.spinner = ["|", "/", "-", "\\"]
        self.idx = 0
        self.message = message
        self.stop_running = False
        self.thread = None

    def spin(self):
        while not self.stop_running:
            sys.stdout.write(f"\r{self.spinner[self.idx % len(self.spinner)]} {self.message}")
            sys.stdout.flush()
            self.idx += 1
            time.sleep(0.1)

    def start(self):
        self.thread = threading.Thread(target=self.spin)
        self.thread.start()

    def stop(self):
        self.stop_running = True
        if self.thread:
            self.thread.join()
        sys.stdout.write("\r" + " " * (len(self.message) + 2) + "\r")
        sys.stdout.flush()

class USOSScraper:
    def __init__(self, base_url="https://web.usos.agh.edu.pl/", verbose=False):
        self.base_url = base_url
        self.verbose = verbose
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))
        self.headers = [
            ('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'),
        ]
        self.opener.addheaders = self.headers

    def fetch_url(self, url):
        if self.verbose:
            print(f"Pobieranie: {url}")
        try:
            with self.opener.open(url) as response:
                return response.read().decode('utf-8')
        except Exception as e:
            if self.verbose:
                print(f"Błąd podczas pobierania {url}: {e}")
            return None

    def get_building_rooms(self, building_id):
        url = f"{self.base_url}kontroler.php?_action=katalog2/jednostki/pokazBudynek&bud_kod={building_id}"
        return self.fetch_url(url)

    def get_room_schedule(self, room_id, date_str=None):
        # date_str powinien być poniedziałkiem danego tygodnia w formacie RRRR-MM-DD
        url = f"{self.base_url}kontroler.php?_action=katalog2/jednostki/pokazSale&sala_id={room_id}"
        if date_str:
            url += f"&plan_week_sel_week={date_str}"
        return self.fetch_url(url)

    def get_all_building_ids(self, mapa_file="mapa-budynkow.html"):
        if not os.path.exists(mapa_file):
            return []
        with open(mapa_file, "r", encoding="utf-8") as f:
            content = f.read()
            # Wyciągamy wszystkie kody budynków z linków bud_kod=XXX
            ids = re.findall(r'bud_kod=([^&\'>]+)', content)
            return sorted(list(set(ids)))

    def find_building_id(self, physical_code, mapa_file="mapa-budynkow.html"):
        if not os.path.exists(mapa_file):
            return physical_code
        
        with open(mapa_file, "r", encoding="utf-8") as f:
            content = f.read()
            
            # Przygotuj warianty kodu (np. B9 i B-9)
            variants = [physical_code]
            if "-" not in physical_code and len(physical_code) > 1 and physical_code[0].isalpha() and physical_code[1].isdigit():
                variants.append(f"{physical_code[0]}-{physical_code[1:]}")
            
            for v in variants:
                # Szukamy linku z bud_kod=XXX który prowadzi do tekstu z kodem fizycznym
                # <a href='...bud_kod=B9'...><b>B-9</b></a>
                pattern = r'bud_kod=([^&\'>]+)[^>]*>\s*(?:<b>)?' + re.escape(v) + r'(?:</b>)?'
                m = re.search(pattern, content, re.IGNORECASE)
                if m:
                    return m.group(1)
                
        return physical_code

class USOSParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rooms = {} # (building_code, room_number) -> capacity
        self.schedules = {} # (building_code, room_number) -> {day_name: [(start, end)]}
        self.room_ids = {} # (building_code, room_number) -> sala_id
        
        self.current_building = None
        self.current_room = None
        self.current_day = None
        
    def handle_starttag(self, tag, attrs):
        if tag == 'timetable-entry':
            attrs_dict = dict(attrs)
            style = attrs_dict.get('style', '')
            start_match = re.search(r'grid-row-start:\s*g(\d{4})', style)
            end_match = re.search(r'grid-row-end:\s*g(\d{4})', style)
            if start_match and end_match and self.current_day and self.current_room and self.current_building:
                start = start_match.group(1)
                end = end_match.group(1)
                start_time = f"{start[:2]}:{start[2:]}"
                end_time = f"{end[:2]}:{end[2:]}"
                key = (self.current_building, self.current_room)
                if key not in self.schedules:
                    self.schedules[key] = {}
                if self.current_day not in self.schedules[key]:
                    self.schedules[key][self.current_day] = []
                self.schedules[key][self.current_day].append((start_time, end_time))

    def handle_data(self, data):
        data = data.strip()
        if not data: return
        
        # Wykrywanie dnia tygodnia w nagłówkach h4
        # Zakładamy, że parser jest wewnątrz tagu h4 (uproszczenie)
        if data in ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"]:
            self.current_day = data

    def parse_file(self, file_path):
        self.current_building = None
        self.current_room = None
        self.current_day = None
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # 1. Identyfikacja budynku/sali z tytułu strony
            title_match = re.search(r'<title>(.*?)</title>', content, re.DOTALL)
            if title_match:
                title_text = title_match.group(1)
                m_room_bud = re.search(r'Sala\s+([A-Z0-9-]+)\s*-\s*Budynek\s+([A-Z0-9-]+)', title_text)
                if m_room_bud:
                    self.current_room = m_room_bud.group(1)
                    self.current_building = m_room_bud.group(2)
                else:
                    m_bud = re.search(r'Budynek\s+([A-Z0-9-]+)', title_text)
                    if m_bud:
                        self.current_building = m_bud.group(1)

            # 2. Wyciąganie sala_id
            if self.current_building and self.current_room:
                m_sid = re.search(r'sala_id["\']?\s*[:=]\s*["\']?(\d+)["\']?', content)
                if m_sid:
                    self.room_ids[(self.current_building, self.current_room)] = m_sid.group(1)

            # 3. Wyciąganie pojemności sal
            if self.current_building and not self.current_room:
                room_matches = re.finditer(r"<td class='strong' style='text-align:center'>([^<]+)</td>\s*<td style='text-align:right'>(\d+)</td>", content)
                for m in room_matches:
                    room_num = m.group(1)
                    capacity = int(m.group(2))
                    self.rooms[(self.current_building, room_num)] = capacity
                
                rows = re.findall(r'<tr>.*?</tr>', content, re.DOTALL)
                for row in rows:
                    m_num = re.search(r"<td class='strong'[^>]*>([^<]+)</td>", row)
                    m_id = re.search(r'sala_id=(\d+)', row)
                    if m_num and m_id:
                        self.room_ids[(self.current_building, m_num.group(1))] = m_id.group(1)

            # 4. Parsowanie planu zajęć
            self.feed(content)

def time_to_minutes(t_str):
    h, m = map(int, t_str.split(':'))
    return h * 60 + m

def is_overlapping(start1, end1, start2, end2):
    return max(time_to_minutes(start1), time_to_minutes(start2)) < min(time_to_minutes(end1), time_to_minutes(end2))

def get_day_of_week_pl(date_obj):
    days = ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"]
    return days[date_obj.weekday()]

def cleanup_cache(cache_dir, verbose=False):
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    current_monday = today - timedelta(days=today.weekday())
    
    if not os.path.exists(cache_dir):
        return
        
    deleted_count = 0
    for filename in os.listdir(cache_dir):
        match = re.search(r'(\d{4}-\d{2}-\d{2})', filename)
        if match:
            file_date_str = match.group(1)
            try:
                file_date = datetime.strptime(file_date_str, "%Y-%m-%d")
                if file_date < current_monday:
                    if verbose:
                        print(f"Usuwanie starego cache: {filename}")
                    os.remove(os.path.join(cache_dir, filename))
                    deleted_count += 1
            except ValueError:
                continue
    
    if verbose and deleted_count > 0:
        print(f"Usunięto {deleted_count} starych plików cache.")

def main():
    parser = argparse.ArgumentParser(description="USOS Room Finder - Znajdź wolną salę.")
    parser.add_argument("--date", help="Data (DD-MM-RRRR), np. 11-05-2026", required=True)
    parser.add_argument("--start", help="Godzina rozpoczęcia (GG:MM), np. 12:00", required=True)
    parser.add_argument("--end", help="Godzina zakończenia (GG:MM), np. 14:00", required=True)
    parser.add_argument("--capacity", type=int, default=0, help="Minimalna liczba miejsc")
    parser.add_argument("--building", help="Kod budynku lub lista (np. B9, D4)")
    parser.add_argument("--dir", default="data", help="Katalog na pobrane dane (domyślnie 'data')")
    parser.add_argument("--renew", action="store_true", help="Wymuś odświeżenie danych (pobierz ponownie)")
    parser.add_argument("--verbose", action="store_true", help="Wyświetlaj szczegółowe informacje o pobieraniu")
    parser.add_argument("--no-cleanup", action="store_true", help="Wyłącz automatyczne czyszczenie starego cache'u")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.dir):
        os.makedirs(args.dir)

    if not args.no_cleanup:
        cleanup_cache(args.dir, verbose=args.verbose)

    try:
        target_date = datetime.strptime(args.date, "%d-%m-%Y")
    except ValueError:
        print("Błąd: Nieprawidłowy format daty. Użyj DD-MM-RRRR.")
        return

    day_name = get_day_of_week_pl(target_date)
    monday_date = target_date - timedelta(days=target_date.weekday())
    monday_str = monday_date.strftime("%Y-%m-%d")
    
    # --- Pobieranie danych ---
    if args.building or (not any(f.endswith('.html') for f in os.listdir(args.dir) if os.path.exists(args.dir)) and not args.building):
        scraper = USOSScraper(verbose=args.verbose)
        spinner = None
        if not args.verbose:
            spinner = Spinner("Pobieranie danych z USOSweb...")
            spinner.start()
        
        try:
            if args.building:
                requested_buildings = [b.strip() for b in args.building.split(',')]
                buildings_to_fetch = []
                for rb in requested_buildings:
                    bud_id = scraper.find_building_id(rb)
                    buildings_to_fetch.append((rb, bud_id))
            else:
                if args.verbose: print("Nie podano budynku. Próba pobrania danych dla wszystkich budynków z mapy...")
                all_ids = scraper.get_all_building_ids()
                buildings_to_fetch = [(bid, bid) for bid in all_ids]
                if not buildings_to_fetch:
                    if spinner: spinner.stop()
                    print("Błąd: Nie znaleziono mapa-budynkow.html. Pobierz plik lub podaj --building.")
                    return

            for physical_name, bud_id in buildings_to_fetch:
                building_cache_file = os.path.join(args.dir, f"building_{bud_id}.html")
                
                if args.renew or not os.path.exists(building_cache_file):
                    if args.verbose: print(f"\n--- Pobieranie danych dla budynku: {physical_name} (USOS ID: {bud_id}) ---")
                    building_html = scraper.get_building_rooms(bud_id)
                    if building_html:
                        with open(building_cache_file, "w", encoding="utf-8") as f:
                            f.write(building_html)
                else:
                    with open(building_cache_file, "r", encoding="utf-8") as f:
                        building_html = f.read()

                if building_html:
                    room_ids = re.findall(r'sala_id=(\d+)', building_html)
                    room_ids = list(set(room_ids))
                    
                    new_rooms_fetched = 0
                    for rid in room_ids:
                        r_file = os.path.join(args.dir, f"room_{bud_id}_{rid}_{monday_str}.html")
                        if args.renew or not os.path.exists(r_file):
                            r_html = scraper.get_room_schedule(rid, monday_str)
                            if r_html:
                                with open(r_file, "w", encoding="utf-8") as f:
                                    f.write(r_html)
                                new_rooms_fetched += 1
                                time.sleep(0.2)
                    
                    if args.verbose and new_rooms_fetched > 0:
                        print(f"Pobrano {new_rooms_fetched} nowych planów sal dla {physical_name} (tydzień {monday_str}).")
        finally:
            if spinner:
                spinner.stop()
    
    # --- Parsowanie danych ---
    usos = USOSParser()
    files_processed = 0
    if os.path.exists(args.dir):
        for filename in os.listdir(args.dir):
            if filename.endswith(".html"):
                usos.parse_file(os.path.join(args.dir, filename))
                files_processed += 1
            
    if files_processed == 0:
        print(f"Błąd: Nie znaleziono plików HTML w {args.dir}. Użyj --building, aby pobrać dane.")
        return

    all_keys = set(usos.rooms.keys()) | set(usos.schedules.keys())
    available_rooms = []
    
    # Przygotuj listę budynków do filtrowania
    filter_buildings = [b.strip().upper() for b in args.building.split(',')] if args.building else None
    
    for key in all_keys:
        b_code, r_num = key
        
        # Poprawione filtrowanie: sprawdź czy budynek jest na liście
        if filter_buildings and b_code.upper() not in filter_buildings:
            continue
            
        capacity = usos.rooms.get(key, 0)
        if capacity < args.capacity:
            continue
        
        busy_slots = usos.schedules.get(key, {}).get(day_name, [])
        is_free = True
        for b_start, b_end in busy_slots:
            if is_overlapping(args.start, args.end, b_start, b_end):
                is_free = False
                break
        
        if is_free:
            available_rooms.append((b_code, r_num, capacity))
            
    print(f"\nSzukanie wolnych sal: {args.date} ({day_name}) {args.start}-{args.end}")
    print(f"Wymagana pojemność: >= {args.capacity}")
    if args.building:
        print(f"Budynek: {args.building}")
    print("-" * 40)
    
    if not available_rooms:
        print("Nie znaleziono dostępnych sal spełniających kryteria.")
    else:
        available_rooms.sort(key=lambda x: (x[0], x[2]))
        print(f"{'Budynek':<10} {'Sala':<10} {'Miejsca':<10} {'Link USOS'}")
        print("-" * 100)
        for b, r, c in available_rooms:
            cap_str = str(c) if c > 0 else "???"
            s_id = usos.room_ids.get((b, r))
            link = f"https://web.usos.agh.edu.pl/kontroler.php?_action=katalog2/jednostki/pokazSale&sala_id={s_id}&plan_week_sel_week={monday_str}" if s_id else "---"
            print(f"{b:<10} {r:<10} {cap_str:<10} {link}")
        print("-" * 100)
        print(f"Znaleziono {len(available_rooms)} wolnych sal.")

if __name__ == "__main__":
    main()
