#import <XCTest/XCTest.h>
#import <TargetConditionals.h>
#if !TARGET_OS_IOS || !TARGET_OS_SIMULATOR || !defined(__arm64__)
#error "The cohost fixture is executed only by an ARM64 iOS simulator"
#endif
/* In-process host App ingress only. The test bundle links none of the SDKs. */
@interface MadDualSQLiteDriver : NSObject
+ (void)run:(void (^)(BOOL))completion;
@end
@interface MadDualSQLiteTests : XCTestCase
@end
@implementation MadDualSQLiteTests
- (void)testInstalledSQLiteProvidersRemainIndependent {
    XCTestExpectation *done=[self expectationWithDescription:@"app scenario complete"];
    [MadDualSQLiteDriver run:^(BOOL success) {
        XCTAssertTrue(success);
        [done fulfill];
    }];
    [self waitForExpectationsWithTimeout:15.0 handler:nil];
}
@end
