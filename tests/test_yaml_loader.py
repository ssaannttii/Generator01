from star_chart_generator.yaml_loader import loads


def test_loads_nested_and_inline():
    yaml_text = """
    root:
      value: 3.5
      list:
        - name: "alpha"
          data: {x: 1, y: 2, z: 3}
        - name: "beta"
          data: [1, 2, 3]
    flag: true
    """
    data = loads(yaml_text)
    assert data["root"]["value"] == 3.5
    assert data["root"]["list"][0]["data"]["x"] == 1
    assert data["root"]["list"][1]["data"] == [1, 2, 3]
    assert data["flag"] is True
