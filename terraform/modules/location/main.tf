# Amazon Location module for Madrid Bus Real-Time Simulator
# Creates route calculator and map resources

# Route calculator for bus routes
resource "aws_location_route_calculator" "bus_routes" {
  calculator_name = "bus-simulator-routes"
  data_source     = "Esri"
  description     = "Route calculator for Madrid bus simulator"

  tags = var.tags
}

# Map resource for Madrid Centro
resource "aws_location_map" "madrid_centro" {
  map_name = "madrid-centro-map"
  description = "Map for Madrid Centro bus routes"

  configuration {
    style = "VectorEsriStreets"
  }

  tags = var.tags
}
