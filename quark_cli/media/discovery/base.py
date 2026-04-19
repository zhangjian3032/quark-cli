"""
DiscoverySource 抽象基类
所有影视发现/元数据源必须实现此接口
"""

from abc import ABC, abstractmethod


class DiscoveryItem:
    """统一的发现结果数据模型"""

    def __init__(
        self,
        source_id="",
        title="",
        original_title="",
        year="",
        media_type="movie",
        rating=0.0,
        vote_count=0,
        overview="",
        poster_path="",
        backdrop_path="",
        genres=None,
        original_language="",
        origin_country=None,
        imdb_id="",
        runtime=0,
        status="",
        tagline="",
        budget=0,
        revenue=0,
        homepage="",
        credits=None,
        extra=None,
    ):
        self.source_id = str(source_id)  # TMDB id
        self.title = title
        self.original_title = original_title
        self.year = year
        self.media_type = media_type  # movie / tv
        self.rating = rating
        self.vote_count = vote_count
        self.overview = overview
        self.poster_path = poster_path
        self.backdrop_path = backdrop_path
        self.genres = genres or []
        self.original_language = original_language
        self.origin_country = origin_country or []
        self.imdb_id = imdb_id
        self.runtime = runtime
        self.status = status
        self.tagline = tagline
        self.budget = budget
        self.revenue = revenue
        self.homepage = homepage
        self.credits = credits or {}  # {"cast": [...], "crew": [...]}
        self.extra = extra or {}

    def __repr__(self):
        return "<DiscoveryItem {} ({}) [{}]>".format(self.title, self.year, self.source_id)


class DiscoveryResult:
    """发现结果分页"""

    def __init__(self, items=None, total=0, page=1, total_pages=1):
        self.items = items or []
        self.total = total
        self.page = page
        self.total_pages = total_pages




class PersonItem:
    """演员/人物统一数据模型"""

    def __init__(
        self,
        person_id="",
        name="",
        original_name="",
        gender=0,
        profile_path="",
        known_for_department="",
        popularity=0.0,
        known_for=None,
        extra=None,
    ):
        self.person_id = str(person_id)
        self.name = name
        self.original_name = original_name or name
        self.gender = gender  # 0=未知, 1=女, 2=男
        self.profile_path = profile_path
        self.known_for_department = known_for_department
        self.popularity = popularity
        self.known_for = known_for or []  # list[DiscoveryItem]
        self.extra = extra or {}

    def __repr__(self):
        return "<PersonItem {} [{}]>".format(self.name, self.person_id)


class PersonResult:
    """人物搜索结果分页"""

    def __init__(self, items=None, total=0, page=1, total_pages=1):
        self.items = items or []  # list[PersonItem]
        self.total = total
        self.page = page
        self.total_pages = total_pages


class DiscoverySource(ABC):
    """
    影视发现源抽象基类
    所有数据源（TMDB / 豆瓣 等）都必须实现此接口
    """

    @property
    @abstractmethod
    def source_name(self):
        # type: () -> str
        """返回数据源名称"""
        ...

    # ── 搜索 & 详情 ──

    @abstractmethod
    def search(self, query, media_type="movie", page=1, year=None):
        # type: (str, str, int, ...) -> DiscoveryResult
        """按关键词搜索"""
        ...

    @abstractmethod
    def get_detail(self, source_id, media_type="movie"):
        # type: (str, str) -> DiscoveryItem
        """获取详情"""
        ...

    @abstractmethod
    def find_by_external_id(self, external_id, external_source="imdb_id"):
        # type: (str, str) -> DiscoveryItem
        """通过外部 ID（如 IMDb ID）查找"""
        ...

    # ── 发现/推荐 ──

    @abstractmethod
    def get_popular(self, media_type="movie", page=1):
        # type: (str, int) -> DiscoveryResult
        """获取热门列表"""
        ...

    @abstractmethod
    def get_top_rated(self, media_type="movie", page=1):
        # type: (str, int) -> DiscoveryResult
        """获取高分列表"""
        ...

    @abstractmethod
    def get_trending(self, media_type="movie", time_window="week"):
        # type: (str, str) -> DiscoveryResult
        """获取趋势列表"""
        ...

    @abstractmethod
    def discover(self, media_type="movie", page=1, **filters):
        # type: (str, int, ...) -> DiscoveryResult
        """高级筛选发现"""
        ...

    # ── 辅助 ──

    @abstractmethod
    def get_genres(self, media_type="movie"):
        # type: (str,) -> dict
        """获取类型列表, 返回 {id: name, ...}"""
        ...


    # ── 演员/人物 ──

    def search_person(self, query, page=1):
        # type: (str, int) -> PersonResult
        """搜索演员/人物 (默认不支持, 子类可覆盖)"""
        return PersonResult()

    def get_person_credits(self, person_id, media_type=None):
        # type: (str, str) -> list
        """获取演员参演作品列表, 返回 list[DiscoveryItem] (默认空)"""
        return []

    def get_person_detail(self, person_id):
        # type: (str,) -> PersonItem
        """获取演员详情 (默认不支持)"""
        return PersonItem()

    def get_poster_url(self, path, size="w500"):
        # type: (str, str) -> str
        """获取海报完整 URL"""
        return ""
