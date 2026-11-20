import UIKit
import Darwin
import Foundation
import MadDB

@main
final class AppDelegate: UIResponder, UIApplicationDelegate {
    var window: UIWindow?

    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?) -> Bool {
        if ProcessInfo.processInfo.arguments.dropFirst().first == "--maddb-two-apps" {
            runStoreAcceptance(Array(ProcessInfo.processInfo.arguments.dropFirst(2)))
        }
        let window = UIWindow(frame: UIScreen.main.bounds)
        let controller = UIViewController()
        controller.view.backgroundColor = .systemBackground
        let label = UILabel()
        label.text = "MadDB binary consumer smoke tests"
        label.textAlignment = .center
        label.translatesAutoresizingMaskIntoConstraints = false
        controller.view.addSubview(label)
        NSLayoutConstraint.activate([
            label.centerXAnchor.constraint(equalTo: controller.view.centerXAnchor),
            label.centerYAnchor.constraint(equalTo: controller.view.centerYAnchor)
        ])
        window.rootViewController = controller
        window.makeKeyAndVisible()
        self.window = window
        return true
    }

    // Test-only command in the sample host. No UI or external endpoints use it.
    private func runStoreAcceptance(_ arguments: [String]) {
        guard arguments.count == 2,
              let nonce = UUID(uuidString: arguments[0]),
              let id = Bundle.main.bundleIdentifier else { return }
        let sentinel: [UInt8]
        switch id {
        case "org.example.maddb.acceptance.a": sentinel = [0, 65, 255, 17]
        case "org.example.maddb.acceptance.b": sentinel = [0, 66, 255, 29]
        default: return
        }
        let phase = arguments[1]
        guard phase == "write" || phase == "read" else { return }
        do {
            let files = FileManager.default
            let support = try files.url(for: .applicationSupportDirectory,
                in: .userDomainMask, appropriateFor: nil, create: true)
            let directory = support.appendingPathComponent("MadDBTwoApps", isDirectory: true)
            try files.createDirectory(at: directory, withIntermediateDirectories: true)
            let file = directory.appendingPathComponent("store.sqlite")
            let result = directory.appendingPathComponent(
                "result-\(nonce.uuidString.lowercased())-\(phase).json")
            let db = try MadDatabase(fileURL: file, namespace: "acceptance")
            defer { try? db.close() }
            if phase == "write" {
                guard try db.get("sentinel") == nil else { return }
                try db.put("sentinel", value: Data(sentinel))
            }
            guard let bytes = try db.get("sentinel"), bytes == Data(sentinel) else { return }
            try db.close()
            let evidence: [String: Any] = [
                "bundle": id, "nonce": nonce.uuidString.lowercased(), "phase": phase,
                "pid": Int(getpid()), "value": Array(bytes)
            ]
            try JSONSerialization.data(withJSONObject: evidence).write(to: result, options: .atomic)
        } catch {
            // No raw error, paths or data printed. The host gate fails if evidence is absent.
        }
    }

}
