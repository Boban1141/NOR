#!/bin/bash
set -euo pipefail
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This script requires macOS with Xcode. It cannot compile iOS on Windows." >&2
  exit 1
fi
cd "$(dirname "$0")"
command -v xcodegen >/dev/null || { echo "Install XcodeGen first: brew install xcodegen" >&2; exit 1; }
xcodebuild -version
mode="${1:-check}"
output="../.runtime/ios-build/$(date +%Y%m%d-%H%M%S)-$$"
mkdir -p "$output"
xcodegen generate
case "$mode" in
  check)
    xcodebuild build -project NOR.xcodeproj -scheme NOR -destination 'generic/platform=iOS' \
      -derivedDataPath "$output/DerivedData" CODE_SIGNING_ALLOWED=NO
    ;;
  test)
    simulator="${2:?Provide the iPhone simulator UDID from xcrun simctl list devices available}"
    xcodebuild test -project NOR.xcodeproj -scheme NOR -destination "platform=iOS Simulator,id=$simulator" \
      -derivedDataPath "$output/DerivedData" CODE_SIGNING_ALLOWED=NO
    ;;
  archive)
    team="${2:?Provide your Apple Developer Team ID}"
    bundle="${3:?Provide your registered unique bundle identifier}"
    [[ "$team" =~ ^[A-Z0-9]{10}$ ]] || { echo "Invalid Team ID" >&2; exit 1; }
    [[ "$bundle" =~ ^[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)+$ ]] || { echo "Invalid bundle identifier" >&2; exit 1; }
    xcodebuild archive -project NOR.xcodeproj -scheme NOR -configuration Release \
      -destination 'generic/platform=iOS' -archivePath "$output/NOR.xcarchive" \
      -allowProvisioningUpdates DEVELOPMENT_TEAM="$team" PRODUCT_BUNDLE_IDENTIFIER="$bundle" CODE_SIGN_STYLE=Automatic
    python3 - "$output/ExportOptions.plist" "$team" <<'PY'
import plistlib
import sys
with open(sys.argv[1], 'wb') as stream:
    plistlib.dump({'method': 'release-testing', 'teamID': sys.argv[2],
                  'signingStyle': 'automatic', 'destination': 'export',
                  'manageAppVersionAndBuildNumber': False}, stream)
PY
    xcodebuild -exportArchive -archivePath "$output/NOR.xcarchive" \
      -exportOptionsPlist "$output/ExportOptions.plist" -exportPath "$output/Export" -allowProvisioningUpdates
    echo "Signed export: $output/Export"
    ;;
  *) echo "Usage: bash Build-NOR.command check | test SIMULATOR_UDID | archive TEAM_ID BUNDLE_ID" >&2; exit 1 ;;
esac
