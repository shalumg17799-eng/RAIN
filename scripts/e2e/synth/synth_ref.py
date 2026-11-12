"""Reference data for the RAIN v0.4 synthetic generator: real Nevada places and ZIP codes, the four fictional
networks and their sites, name lists. Coordinates are approximate town centres (public knowledge)."""
from datetime import date

AS_OF = date(2026, 11, 3)            # the demo's "today": the Q3 reconciliation has just arrived
CONTRACT_START = date(2026, 1, 1)
MONTHS = [(2026, m) for m in range(1, 10)]                      # Jan..Sep 2026: the Q3 reconciliation window
LV_MONTHS = [(2025, 10), (2025, 11), (2025, 12)] + MONTHS       # trailing 12 months for low-value care
MONTH_LABEL = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun", 7: "Jul", 8: "Aug", 9: "Sep",
               10: "Oct", 11: "Nov", 12: "Dec"}
LBP_ICD = "M54.50"
COUNTY_FIPS = {"elko": "32007", "humboldt": "32013", "lander": "32015", "pershing": "32027", "whitePine": "32033",
               "churchill": "32001"}


def month_days(y, m):
    nxt = date(y + (m == 12), m % 12 + 1, 1)
    return (nxt - date(y, m, 1)).days


# zip -> county, place, lat, lon, frontier flag, typical drive minutes to the nearest network town site
ZIPS = {
    "89801": dict(county="elko", place="Elko", lat=40.8324, lon=-115.7631, frontier=False, drive=10),
    "89815": dict(county="elko", place="Spring Creek", lat=40.7266, lon=-115.5859, frontier=False, drive=20),
    "89822": dict(county="elko", place="Carlin", lat=40.7138, lon=-116.1040, frontier=False, drive=25),
    "89835": dict(county="elko", place="Wells", lat=41.1116, lon=-114.9645, frontier=False, drive=10),
    "89825": dict(county="elko", place="Jackpot", lat=41.9832, lon=-114.6745, frontier=True, drive=100),
    "89826": dict(county="elko", place="Jarbidge", lat=41.8722, lon=-115.4298, frontier=True, drive=118),
    "89832": dict(county="elko", place="Owyhee", lat=41.9457, lon=-116.0979, frontier=True, drive=112),
    "89831": dict(county="elko", place="Mountain City", lat=41.8380, lon=-115.9620, frontier=True, drive=96),
    "89823": dict(county="elko", place="Deeth", lat=41.0663, lon=-115.2742, frontier=True, drive=62),
    "89445": dict(county="humboldt", place="Winnemucca", lat=40.9730, lon=-117.7357, frontier=False, drive=10),
    "89404": dict(county="humboldt", place="Denio", lat=41.9896, lon=-118.6346, frontier=True, drive=105),
    "89421": dict(county="humboldt", place="McDermitt", lat=41.9988, lon=-117.7140, frontier=True, drive=78),
    "89425": dict(county="humboldt", place="Orovada", lat=41.5671, lon=-117.7840, frontier=True, drive=62),
    "89414": dict(county="humboldt", place="Golconda", lat=40.9566, lon=-117.4920, frontier=False, drive=28),
    "89820": dict(county="lander", place="Battle Mountain", lat=40.6421, lon=-116.9343, frontier=False, drive=10),
    "89310": dict(county="lander", place="Austin", lat=39.4930, lon=-117.0690, frontier=True, drive=96),
    "89419": dict(county="pershing", place="Lovelock", lat=40.1794, lon=-118.4735, frontier=False, drive=10),
    "89418": dict(county="pershing", place="Imlay", lat=40.6582, lon=-118.1529, frontier=True, drive=64),
    "89301": dict(county="whitePine", place="Ely", lat=39.2474, lon=-114.8886, frontier=False, drive=10),
    "89318": dict(county="whitePine", place="McGill", lat=39.4055, lon=-114.7786, frontier=False, drive=22),
    "89311": dict(county="whitePine", place="Baker", lat=39.0135, lon=-114.1225, frontier=True, drive=82),
    "89317": dict(county="whitePine", place="Lund", lat=38.8627, lon=-115.0067, frontier=True, drive=66),
    "89406": dict(county="churchill", place="Fallon", lat=39.4735, lon=-118.7774, frontier=False, drive=10),
    "89496": dict(county="churchill", place="Fallon Station", lat=39.4171, lon=-118.7051, frontier=False, drive=15),
}
# the six frontier places with too little broadband for video (PRD story; computed from broadband_coverage)
LOW_BB_ZIPS = ["89826", "89404", "89310", "89418", "89311", "89832"]

NETWORKS_INFO = [
    dict(id="sbch", name="Sierra Basin Community Health", short="Sierra Basin", hq="elko", payer="High Desert Health Plan", award=2_600_000),
    dict(id="gbrc", name="Great Basin Rural Clinics", short="Great Basin", hq="churchill", payer="Silver Sage Health Plan", award=1_900_000,
         members_by_county={"churchill": 5900, "elko": 2100}),
    dict(id="hrhp", name="Humboldt River Health Partners", short="Humboldt River", hq="humboldt", payer="Silver Sage Health Plan",
         award=1_700_000, members_by_county={"humboldt": 3500, "pershing": 1400, "lander": 1900, "elko": 1200}),
    dict(id="rvfh", name="Ruby Valley Family Health", short="Ruby Valley", hq="elko", payer="High Desert Health Plan", award=1_500_000,
         members_by_county={"elko": 3600, "whitePine": 2600}),
]
NETWORK_SITES = {
    "sbch": [dict(id="elko", town="Elko", zip="89801"), dict(id="wells", town="Wells", zip="89835"),
             dict(id="winnemucca", town="Winnemucca", zip="89445"), dict(id="battleMountain", town="Battle Mountain", zip="89820"),
             dict(id="lovelock", town="Lovelock", zip="89419"), dict(id="ely", town="Ely", zip="89301"),
             dict(id="fallon", town="Fallon", zip="89406")],
    "gbrc": [dict(id="gbrc-fallon", town="Fallon", zip="89406"), dict(id="gbrc-fallon-station", town="Fallon Station", zip="89496"),
             dict(id="gbrc-elko", town="Elko", zip="89801"), dict(id="gbrc-carlin", town="Carlin", zip="89822")],
    "hrhp": [dict(id="hrhp-winnemucca", town="Winnemucca", zip="89445"), dict(id="hrhp-lovelock", town="Lovelock", zip="89419"),
             dict(id="hrhp-battle-mountain", town="Battle Mountain", zip="89820")],
    "rvfh": [dict(id="rvfh-elko", town="Elko", zip="89801"), dict(id="rvfh-spring-creek", town="Spring Creek", zip="89815"),
             dict(id="rvfh-ely", town="Ely", zip="89301"), dict(id="rvfh-mcgill", town="McGill", zip="89318")],
}

FIRST = {
    "en": ["James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda", "David", "Elizabeth", "William", "Barbara",
           "Richard", "Susan", "Joseph", "Jessica", "Thomas", "Sarah", "Charles", "Karen", "Daniel", "Nancy", "Matthew", "Lisa",
           "Anthony", "Betty", "Mark", "Sandra", "Steven", "Ashley", "Paul", "Donna", "Andrew", "Carol", "Joshua", "Michelle",
           "Kenneth", "Emily", "Kevin", "Amanda", "Brian", "Melissa", "George", "Deborah", "Timothy", "Stephanie", "Ronald", "Rebecca"],
    "es": ["Jose", "Maria", "Juan", "Guadalupe", "Luis", "Rosa", "Carlos", "Ana", "Jorge", "Lucia", "Miguel", "Carmen", "Pedro",
           "Teresa", "Francisco", "Elena", "Antonio", "Isabel", "Manuel", "Sofia", "Ricardo", "Alicia", "Fernando", "Gloria"],
}
LAST = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez",
        "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
        "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King", "Wright",
        "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell",
        "Mitchell", "Carter", "Roberts", "Morales", "Reyes", "Cruz", "Ortiz", "Gomez", "Ruiz", "Diaz", "Chavez", "Jim", "Begay"]
