from services.location_matcher import match_location_coordinates, match_location_text


def main() -> None:
    toronto_geo = match_location_coordinates(43.6532, -79.3832)
    peel_text = match_location_text("Peel G.E. Booth | Peel Region")
    outside = match_location_coordinates(49.2827, -123.1207)

    print("Toronto coordinates:", toronto_geo)
    print("Peel text:", peel_text)
    print("Vancouver coordinates (should reject):", outside)


if __name__ == "__main__":
    main()
