from product_radar_parser.discovery import ProductCandidate, _dedupe, _needs_more, _next_markers, _payload_marker, parse_leaderboard_html


def test_parse_week_leaderboard_top_one():
    html = """
    <div class="products__period">13 апреля - 19 апреля, 2026</div>
    <div class="products__item card">
      <a class="product-bg-link" href="/product/smink-2/"></a>
      <button class="upvote" data-id="11459" data-votes="41"></button>
      <a class="card__comments">9</a>
    </div>
    <div class="products__item card">
      <a class="product-bg-link" href="/product/second/"></a>
      <button class="upvote" data-id="2" data-votes="4"></button>
      <a class="card__comments">1</a>
    </div>
    """
    candidates = parse_leaderboard_html(html, "https://productradar.ru", top_k=1)

    assert len(candidates) == 1
    assert candidates[0].product_url == "https://productradar.ru/product/smink-2/"
    assert candidates[0].product_id == 11459
    assert candidates[0].votes_total == 41
    assert candidates[0].discussion_count == 9


def test_parse_comment_count_with_svg_and_js_next_markers():
    html = """
    <time class="products__period">13 апреля - 19 апреля, 2026</time>
    <article class="products__item card">
      <a class="product-bg-link" href="/product/smink-2/"></a>
      <a class="card__comments"><svg></svg> 9 </a>
      <button class="upvote" data-votes="44" data-id="11459"></button>
    </article>
    <script id="handle-more-button-js-extra">
    var loadMoreHome = {"nextPeriod":"1","nextPage":"0","groupBy":"week","url":"https://productradar.ru/wp-admin/"};
    </script>
    """

    candidates = parse_leaderboard_html(html, "https://productradar.ru", top_k=5)

    assert candidates[0].discussion_count == 9
    assert _next_markers(html) == ("1", "0")


def test_empty_period_does_not_count_as_real_period():
    candidates = [
        ProductCandidate("/a", period="Апрель 2026"),
        ProductCandidate("/b", period=""),
    ]

    assert _needs_more(candidates, periods=2, top_k=1)


def test_partially_filled_period_still_counts_as_period():
    candidates = [
        ProductCandidate("/a", period="week 1"),
        ProductCandidate("/b", period="week 2"),
    ]

    assert not _needs_more(candidates, periods=2, top_k=10)


def test_dedupe_does_not_count_duplicate_toward_top_k():
    candidates = [
        ProductCandidate("/a", period="week 1"),
        ProductCandidate("/a", period="week 1"),
        ProductCandidate("/b", period="week 1"),
    ]

    selected = _dedupe(candidates, periods=1, top_k=2)

    assert [candidate.product_url for candidate in selected] == ["/a", "/b"]


def test_payload_marker_preserves_zero_page():
    assert _payload_marker({"next_page": 0}, "next_page") == "0"
    assert _payload_marker({"next_period": 2}, "next_period") == "2"
    assert _payload_marker({}, "next_page") == ""
