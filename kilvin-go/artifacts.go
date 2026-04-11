package main

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
	"path/filepath"
	"sort"

	"gopkg.in/yaml.v3"
)

func canonicalYAML(input any) ([]byte, error) {
	return yaml.Marshal(input)
}

type ArtifactStore struct {
	Root string
}

func NewArtifactStore(rootURI string) ArtifactStore {
	root := rootURI
	if root == "" {
		root = "file://./.kilvin-artifacts"
	}
	if len(root) >= 7 && root[:7] == "file://" {
		root = root[7:]
	}
	_ = os.MkdirAll(root, 0o755)
	return ArtifactStore{Root: root}
}

func (s ArtifactStore) path(runID string, runAttempt int, name string) string {
	return filepath.Join(s.Root, runID, fmt.Sprintf("%d", runAttempt), "artifacts", name)
}

func (s ArtifactStore) WriteYAMLArtifact(runID string, runAttempt int, name string, payload any) (StepIOArtifact, error) {
	data, err := canonicalYAML(payload)
	if err != nil {
		return StepIOArtifact{}, err
	}
	if len(data) > 0 {
		// Ensure stable bytes for reproducible checksum values.
		// YAML output is deterministic enough for this scoped use because every artifact payload is built from typed Go structs.
		var canonical map[string]any
		if err := yaml.Unmarshal(data, &canonical); err == nil {
			reordered, marshalErr := yaml.Marshal(canonical)
			if marshalErr == nil {
				data = reordered
			}
		}
	}
	sum := sha256.Sum256(data)
	out := StepIOArtifact{
		URI:            "file://" + s.path(runID, runAttempt, name),
		Format:         "yaml",
		ChecksumSHA256: hex.EncodeToString(sum[:]),
		SizeBytes:      int64(len(data)),
	}
	if err := os.MkdirAll(filepath.Dir(filepath.Clean(out.URI[7:])), 0o755); err != nil {
		return StepIOArtifact{}, err
	}
	if err := os.WriteFile(out.URI[7:], data, 0o644); err != nil {
		return StepIOArtifact{}, err
	}
	return out, nil
}

func canonicalMap(in map[string]any) map[string]any {
	keys := make([]string, 0, len(in))
	for k := range in {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	out := make(map[string]any, len(in))
	for _, k := range keys {
		out[k] = in[k]
	}
	return out
}
