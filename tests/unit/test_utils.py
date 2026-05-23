"""
Unit tests for Coact API core functionality.
"""

from utils.nl import NodeList


class TestNodeList:
    """Test the NodeList utility for parsing SLURM node lists."""

    def test_single_node(self):
        """Test parsing a single node name."""
        nodelist = NodeList("psana1309")
        assert len(nodelist.nodes) == 1
        assert "psana1309" in nodelist.nodes

    def test_range_expansion(self):
        """Test parsing a range of nodes."""
        nodelist = NodeList("psana[1514-1517]")
        expected = {"psana1514", "psana1515", "psana1516", "psana1517"}
        assert nodelist.nodes == expected

    def test_complex_range(self):
        """Test parsing complex ranges with multiple segments."""
        nodelist = NodeList("psana[1208-1210,1213-1219,1305-1306,1313,1315,1319,1402,1404-1405,1415]")

        # Should contain all individual nodes from the ranges
        assert "psana1208" in nodelist.nodes
        assert "psana1209" in nodelist.nodes
        assert "psana1210" in nodelist.nodes
        assert "psana1213" in nodelist.nodes
        assert "psana1219" in nodelist.nodes
        assert "psana1305" in nodelist.nodes
        assert "psana1313" in nodelist.nodes
        assert "psana1315" in nodelist.nodes
        assert "psana1415" in nodelist.nodes

        # Should not contain nodes outside the ranges
        assert "psana1211" not in nodelist.nodes
        assert "psana1212" not in nodelist.nodes

    def test_sorted_output(self):
        """Test that sorted() returns nodes in numerical order."""
        nodelist = NodeList("psana[1315,1305,1319]")
        sorted_nodes = nodelist.sorted()
        assert sorted_nodes == ["psana1305", "psana1315", "psana1319"]
