module github.com/temporalio/kilvin-go

go 1.24.0

require (
	go.temporal.io/sdk v1.0.0
	gopkg.in/yaml.v3 v3.0.1
)

replace go.temporal.io/sdk => ../sdk-go
